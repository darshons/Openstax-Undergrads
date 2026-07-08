"""Thin Gemini wrapper for the manim pipeline (text and text+image calls).

Uses the google.genai SDK like video_generator/veo_api.py, with the same
transient-error retry discipline.
"""

import os
import time

from google import genai
from google.genai import errors as genai_errors

DEFAULT_MODEL = "gemini-2.5-pro"
# gRPC codes considered transient (mirrors veo_api.py): INTERNAL, RESOURCE_EXHAUSTED, UNAVAILABLE
RETRYABLE_CODES = {13, 8, 14, 429, 500, 503}
MAX_ATTEMPTS = 4


class GeminiClient:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))

    def generate(self, prompt: str, image=None, label: str = "") -> str:
        """One completion. `image` may be a PIL Image (for the visual critic)."""
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
                if getattr(e, "code", None) not in RETRYABLE_CODES or attempt == MAX_ATTEMPTS:
                    raise
                print(f"[gemini:{label}] transient error {e.code}, retry {attempt}/{MAX_ATTEMPTS} in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
        raise last_err
