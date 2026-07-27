import os
import time
from datetime import datetime
from pathlib import Path

from .logging_utils import OUTPUT_DIR

# MODELS
VEO_MODELS = {
    "veo-3.1": "veo-3.1-generate-preview",
    "veo-3.1-fast": "veo-3.1-fast-generate-preview",
    "veo-3.1-lite": "veo-3.1-lite-generate-preview",
    "veo-2": "veo-2.0-generate-001",
}

# STITCH PIPELINE SETTINGS
# MODEL = "veo-3.1-generate-preview"
# MODEL_KEY = "veo-3.1"

MODEL = "veo-3.1-fast-generate-preview"
MODEL_KEY = "veo-3.1-fast"

# DEPRECATED: the Veo backend is superseded by the local ComfyUI Wan2.2
# backend (video_generator/local_api.py), which is the CLI default. This
# module is kept selectable via `--model veo-*` and requires GEMINI_API_KEY.


def set_model(model_key: str):
    """Select which (deprecated) Veo model this module targets. Must be
    called before video_generator.pipeline is imported — pipeline binds
    MODEL_KEY by value at import time for logging/cost lookups."""
    global MODEL, MODEL_KEY
    if model_key not in VEO_MODELS:
        raise ValueError(f"Unknown Veo model {model_key!r}; choose from {sorted(VEO_MODELS)}")
    MODEL = VEO_MODELS[model_key]
    MODEL_KEY = model_key


RESOLUTION = "720p"
ASPECT_RATIO = "16:9"
POLL_INTERVAL = 10

# Paths to reference image PNGs for character consistency (first clip only).
# Place files in reference_images/ and list them here, e.g.:
#   REFERENCE_IMAGES = ["reference_images/maya.png", "reference_images/carl.png"]
# REFERENCE_IMAGES = [
#     "reference_images/maya.png",
#     "reference_images/carl.png",
#     "reference_images/background_reference_image.png",
# ]
REFERENCE_IMAGES = []

# DURATION CONSTRAINTS
VALID_FIRST_CLIP_SECONDS = (4, 6, 8)
EXTENSION_SECONDS = 7
MAX_CLIPS = 21
# PROCESSING SETTLE
EXTENSION_SETTLE_SECONDS = 15
# TRANSIENT RETRY
MAX_GENERATION_RETRIES = 2
RETRY_BASE_DELAY_SECONDS = 30
RETRYABLE_ERROR_CODES = {13}  # RESOURCE_EXHAUSTED, INTERNAL, UNAVAILABLE

# $/second of output video. Veo 3.1 models generate audio by default → Video+Audio tier.
# Source: https://cloud.google.com/generative-ai-studio/pricing
VEO_COST_PER_SECOND = {
    "veo-3.1": {"720p": 0.40, "1080p": 0.40, "4k": 0.60},
    "veo-3.1-fast": {"720p": 0.10, "1080p": 0.12, "4k": 0.30},
    "veo-3.1-lite": {"720p": 0.05, "1080p": 0.08},
    "veo-2": {"720p": 0.50},
}


class _VeoRetryableError(RuntimeError):
    """A transient Veo failure (code 13 INTERNAL / overload) worth retrying."""


class _VeoExhaustedError(RuntimeError):
    """Raised when generate_with_retry exhausts all attempts. Carries attempts_used."""

    def __init__(self, label: str, attempts_used: int, last_err: Exception):
        super().__init__(
            f"{label}: still failing after {attempts_used} attempts. Last error: {last_err}"
        )
        self.attempts_used = attempts_used


class ClipEvalFailedError(RuntimeError):
    """Raised by the pipeline when a clip still fails transcript-eval after all retries."""


def _format_operation_error(error) -> str:
    """Render a finished operation's error as "[code] message" — the raw
    object's default __str__/__repr__ (as previously interpolated straight
    into the exception message) isn't guaranteed to surface Veo's actual
    code/message, so extract them explicitly the same way
    _is_retryable_operation_error already does."""
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message", "") or ""
    else:
        code = getattr(error, "code", None)
        message = getattr(error, "message", "") or ""
    return f"[{code}] {message}" if (code is not None or message) else str(error)


def _is_retryable_operation_error(error):
    """True if a finished operation's error is a transient backend failure worth
    retrying (code 13 INTERNAL, 8 RESOURCE_EXHAUSTED, 14 UNAVAILABLE, or an
    'internal server issue' / 'try again' message)."""
    if not error:
        return False
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message", "") or ""
    else:
        code = getattr(error, "code", None)
        message = getattr(error, "message", "") or ""
    if code in RETRYABLE_ERROR_CODES:
        return True
    msg = message.lower()
    return (
        "internal server issue" in msg or "internal error" in msg or "try again" in msg
    )


def _classify_error(error: Exception) -> str:
    if isinstance(error, ClipEvalFailedError):
        return "content_eval_failed"
    msg = str(error).lower()
    if "content" in msg or "policy" in msg or "safety" in msg:
        return "content_policy"
    if "quota" in msg or "resource_exhausted" in msg or "rate limit" in msg:
        return "quota"
    if isinstance(error, _VeoRetryableError) or "transient" in msg:
        return "transient"
    return "unknown"


def estimate_cost(
    model_key: str, resolution: str, duration_seconds: float
) -> float | None:
    rate = VEO_COST_PER_SECOND.get(model_key, {}).get(resolution)
    if rate is None or duration_seconds is None:
        return None
    return round(rate * duration_seconds, 4)


def get_video_duration(path: str) -> float | None:
    try:
        from moviepy import VideoFileClip

        clip = VideoFileClip(path)
        dur = clip.duration
        clip.close()
        return round(dur, 2)
    except Exception:
        return None


def create_reference_image_configs(reference_images: list) -> list:
    from google.genai.types import VideoGenerationReferenceImage, Image as GenaImage

    configs = []
    for img_path in reference_images:
        with open(img_path, "rb") as f:
            image_bytes = f.read()
        configs.append(
            VideoGenerationReferenceImage(
                image=GenaImage(image_bytes=image_bytes, mime_type="image/png"),
                reference_type="asset",
            )
        )
    return configs


def poll_until_done(client, operation):
    """Poll operation until Veo finishes generating."""
    print("  Waiting for generation ", end="", flush=True)
    while not operation.done:
        time.sleep(POLL_INTERVAL)
        operation = client.operations.get(operation)
        print(".", end="", flush=True)

    if getattr(operation, "error", None):
        if _is_retryable_operation_error(operation.error):
            print(" failed (transient).")
            raise _VeoRetryableError(
                f"Veo generation failed (transient): {_format_operation_error(operation.error)}"
            )
        print(" failed.")
        raise RuntimeError(f"Veo generation failed: {_format_operation_error(operation.error)}")
    if not getattr(operation, "response", None) or not getattr(
        operation.response, "generated_videos", None
    ):
        print(" failed (empty response).")
        raise RuntimeError(
            "Veo returned no videos — operation completed but response is empty. "
            "Possible causes: content policy rejection, API quota, or transient generation failure."
        )
    print(" done!")
    return operation


def generate_with_retry(generate_fn, label):
    """Run a generate+poll thunk, retrying transient code 13 INTERNAL failures
    with exponential backoff. generate_fn must (re)issue the generate_videos call
    and return the polled-to-done video object. On a transient failure we wait and
    re-issue the whole call (a fresh operation), per Veo's 'try again in a few
    minutes' guidance. Non-transient errors (content policy, etc.) propagate
    immediately.

    Returns (video_obj, attempts_used, recovered_error) — recovered_error is
    None on a clean first-try success, or the last transient error's message
    if the eventual success followed one or more retries (otherwise that
    error was only ever visible in console output, never in the log).
    """
    last_err = None
    for attempt in range(1, MAX_GENERATION_RETRIES + 1):
        try:
            video_obj = generate_fn()
            recovered_error = (
                f"{last_err} (retried, succeeded on attempt {attempt}/{MAX_GENERATION_RETRIES})"
                if last_err else None
            )
            return video_obj, attempt, recovered_error
        except _VeoRetryableError as e:
            last_err = e
            if attempt == MAX_GENERATION_RETRIES:
                break
            delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(
                f"\n  {label}: transient backend failure "
                f"(attempt {attempt}/{MAX_GENERATION_RETRIES}). "
                f"Waiting {delay}s before retrying...\n    [{e}]"
            )
            time.sleep(delay)
    raise _VeoExhaustedError(label, MAX_GENERATION_RETRIES, last_err)


def generate_first_clip(
    client, prompt, clip_index=1, reference_images=None, duration_seconds=8, model=None
):
    """
    Generates the opening clip for a scene.

    duration_seconds: 4, 6, or 8 - only when no reference images are used.
    Asset/subject reference images force 8 second duration for veo-3.1-generate-preview,
    so the value will get overridden in that case.

    model: overrides the module-level MODEL constant (e.g. for running a cheaper
    model during exploration). Defaults to MODEL when omitted.

    Returns (video_obj, attempts_used, recovered_error).
    """
    from google.genai import types

    model = model or MODEL

    ref_image_configs = []
    if reference_images:
        ref_image_configs = create_reference_image_configs(reference_images)

    if ref_image_configs and duration_seconds != 8:
        print(
            f" Note: reference images force 8s; ignoring duration_seconds={duration_seconds}"
        )
        duration_seconds = 8

    print(f"\n Generating clip {clip_index} (first clip, {duration_seconds}s, model={model})...")

    def _attempt():
        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio=ASPECT_RATIO,
                resolution=RESOLUTION,
                number_of_videos=1,
                duration_seconds=duration_seconds,
                reference_images=ref_image_configs if ref_image_configs else None,
            ),
        )
        operation = poll_until_done(client, operation)
        return operation.response.generated_videos[0].video

    return generate_with_retry(_attempt, label=f"clip {clip_index}")


def generate_extension_clip(client, prompt, previous_video_obj, clip_index, model=None):
    """
    Extend the previous Veo video by one ~7s hop. Duration is NOT configurable on
    extension — the API returns a fixed ~7s continuation.

    The Veo API rejects reference_images when video= (extension mode) is also provided —
    the two are mutually exclusive. Character consistency on extension clips is enforced
    through the is_continuation text anchor in build_veo_prompt instead.

    model: overrides the module-level MODEL constant (e.g. for running a cheaper
    model during exploration). Defaults to MODEL when omitted.

    Returns (video_obj, attempts_used, recovered_error).
    """
    from google.genai import types

    model = model or MODEL

    print(f"\n  Generating clip {clip_index} (extension, ~7s, model={model})...")

    def _attempt():
        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            video=previous_video_obj,
            config=types.GenerateVideosConfig(
                aspect_ratio=ASPECT_RATIO,
                resolution=RESOLUTION,
                number_of_videos=1,
            ),
        )
        operation = poll_until_done(client, operation)
        return operation.response.generated_videos[0].video

    return generate_with_retry(_attempt, label=f"clip {clip_index}")


def download_video(client, video_obj, output_file):
    """Download one Veo video object. Called once, on the final combined
    video — never on intermediate extension handles."""
    video_data = client.files.download(file=video_obj.uri)
    with open(output_file, "wb") as f:
        f.write(video_data)
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  Saved: {output_file} ({size_mb:.1f} MB)")
    return output_file
