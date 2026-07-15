"""Thin Gemini wrapper for the manim pipeline (text and text+image calls).

Uses the google.genai SDK like video_generator/veo_api.py, with the same
transient-error retry discipline.
"""

import os
import time

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

DEFAULT_MODEL = "gemini-2.5-pro"
# gRPC codes considered transient (mirrors veo_api.py): INTERNAL, RESOURCE_EXHAUSTED, UNAVAILABLE
RETRYABLE_CODES = {13, 8, 14, 429, 500, 503}
MAX_ATTEMPTS = 4
# Per-request cap so one stuck call fails fast and RETRIES instead of hanging
# the whole serial pipeline. A read timeout here is treated as transient (a
# large assets.py / scene generation occasionally exceeds it), so it must be
# generous enough that a normal long generation completes.
REQUEST_TIMEOUT_MS = 600_000
# Transport-level failures worth retrying (the SDK does not wrap these in APIError).
_RETRYABLE_TRANSPORT = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
)


class GeminiClient:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self.client = genai.Client(
            api_key=api_key or os.environ.get("GEMINI_API_KEY"),
            http_options=genai_types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )

    def generate(self, prompt: str, image=None, label: str = "") -> str:
        """One completion. `image` may be a PIL Image (for the visual critic).
        Retries transient API errors AND transport timeouts — an unretried
        timeout previously crashed the whole pipeline."""
        contents = [prompt] if image is None else [prompt, image]
        delay = 5.0
        last_err = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents
                )
                text = response.text
                if not text:
                    raise RuntimeError(f"Empty Gemini response ({label or 'generate'})")
                return text
            except genai_errors.APIError as e:
                last_err = e
                if (
                    getattr(e, "code", None) not in RETRYABLE_CODES
                    or attempt == MAX_ATTEMPTS
                ):
                    raise
                print(
                    f"[gemini:{label}] transient error {e.code}, retry {attempt}/{MAX_ATTEMPTS} in {delay:.0f}s"
                )
                time.sleep(delay)
                delay *= 2
            except _RETRYABLE_TRANSPORT as e:
                last_err = e
                if attempt == MAX_ATTEMPTS:
                    raise
                print(
                    f"[gemini:{label}] transport timeout, retry {attempt}/{MAX_ATTEMPTS} in {delay:.0f}s"
                )
                time.sleep(delay)
                delay *= 2
        raise last_err
