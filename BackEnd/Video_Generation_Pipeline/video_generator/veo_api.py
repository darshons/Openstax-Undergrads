import os
import time
from datetime import datetime
from pathlib import Path

from .logging_utils import OUTPUT_DIR, log_generation

#MODELS
VEO_MODELS = {
    "veo-3.1":      "veo-3.1-generate-preview",
    "veo-3.1-fast": "veo-3.1-fast-generate-preview",
    "veo-3.1-lite": "veo-3.1-lite-generate-preview",
    "veo-2":        "veo-2.0-generate-001",
}

DEFAULT_MODEL = "veo-3.1"
DEFAULT_RESOLUTION = "720p"
DEFAULT_ASPECT = "16:9"

#STITCH PIPELINE SETTINGS
MODEL = "veo-3.1-generate-preview"
MODEL_KEY = "veo-3.1"
RESOLUTION = "720p"
ASPECT_RATIO = "16:9"
POLL_INTERVAL = 10

#DURATION CONSTRAINTS
VALID_FIRST_CLIP_SECONDS = (4, 6, 8)
EXTENSION_SECONDS = 7
MAX_CLIPS = 21
#PROCESSING SETTLE
EXTENSION_SETTLE_SECONDS = 15
#TRANSIENT RETRY
MAX_GENERATION_RETRIES = 4
RETRY_BASE_DELAY_SECONDS = 30
RETRYABLE_ERROR_CODES = {13}

# $/second of output video. Veo 3.1 models generate audio by default → Video+Audio tier.
# Source: https://cloud.google.com/generative-ai-studio/pricing
VEO_COST_PER_SECOND = {
    "veo-3.1":      {"720p": 0.40, "1080p": 0.40, "4k": 0.60},
    "veo-3.1-fast": {"720p": 0.10, "1080p": 0.12, "4k": 0.30},
    "veo-3.1-lite": {"720p": 0.05, "1080p": 0.08},
    "veo-2":        {"720p": 0.50},
}


class _VeoRetryableError(RuntimeError):
    """A transient Veo failure (code 13 INTERNAL / overload) worth retrying."""


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
    return "internal server issue" in msg or "internal error" in msg or "try again" in msg


def _classify_error(error: Exception) -> str:
    msg = str(error).lower()
    if "content" in msg or "policy" in msg or "safety" in msg:
        return "content_policy"
    if "quota" in msg or "resource_exhausted" in msg or "rate limit" in msg:
        return "quota"
    if isinstance(error, _VeoRetryableError) or "transient" in msg:
        return "transient"
    return "unknown"


def estimate_cost(model_key: str, resolution: str, duration_seconds: float) -> float | None:
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
            raise _VeoRetryableError(f"Veo generation failed (transient): {operation.error}")
        print(" failed.")
        raise RuntimeError(f"Veo generation failed: {operation.error}")
    if not getattr(operation, "response", None) or not getattr(operation.response, "generated_videos", None):
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

    Returns (video_obj, attempts_used).
    """
    last_err = None
    for attempt in range(1, MAX_GENERATION_RETRIES + 1):
        try:
            return generate_fn(), attempt
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
    raise RuntimeError(
        f"{label}: still failing after {MAX_GENERATION_RETRIES} attempts. "
        f"Last error: {last_err}"
    )


def generate_first_clip(client, prompt, clip_index=1, reference_images=None, duration_seconds=8):
    """
    Generates the opening clip for a scene.

    duration_seconds: 4, 6, or 8 - only when no reference images are used.
    Asset/subject reference images force 8 second duration for veo-3.1-generate-preview,
    so the value will get overridden in that case.

    Returns (video_obj, attempts_used).
    """
    from google.genai import types

    ref_image_configs = []
    if reference_images:
        ref_image_configs = create_reference_image_configs(reference_images)

    if ref_image_configs and duration_seconds != 8:
        print(f" Note: reference images force 8s; ignoring duration_seconds={duration_seconds}")
        duration_seconds = 8

    print(f"\n Generating clip {clip_index} (first clip, {duration_seconds}s)...")

    def _attempt():
        operation = client.models.generate_videos(
            model=MODEL,
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


def generate_extension_clip(client, prompt, previous_video_obj, clip_index):
    """
    Extend the previous Veo video by one ~7s hop. Duration is NOT configurable on
    extension — the API returns a fixed ~7s continuation.

    The Veo API rejects reference_images when video= (extension mode) is also provided —
    the two are mutually exclusive. Character consistency on extension clips is enforced
    through the is_continuation text anchor in build_veo_prompt instead.

    Returns (video_obj, attempts_used).
    """
    from google.genai import types

    print(f"\n  Generating clip {clip_index} (extension, ~7s)...")

    def _attempt():
        operation = client.models.generate_videos(
            model=MODEL,
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


def generate_video(
    client,
    prompt: str,
    scene_id: int,
    model_key: str = DEFAULT_MODEL,
    resolution: str = DEFAULT_RESOLUTION,
    aspect_ratio: str = DEFAULT_ASPECT,
    prompt_override: str = None,
    reference_images: list = None,
    poll_interval: int = 10,
) -> dict:
    """
    Generate a single video from a prompt using Veo.
    Returns a log entry dict with results.
    """
    from google.genai import types

    final_prompt = prompt_override if prompt_override else prompt

    model_api_name = VEO_MODELS.get(model_key)
    if not model_api_name:
        raise ValueError(f"Unknown model key '{model_key}'. Choose from: {list(VEO_MODELS.keys())}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = str(OUTPUT_DIR / f"scene{scene_id}_{model_key}_{timestamp}.mp4")
    ref_count = len(reference_images) if reference_images else 0

    print(f"\n{'─'*60}")
    print(f"  Scene:      {scene_id}")
    print(f"  Model:      {model_key} ({model_api_name})")
    print(f"  Resolution: {resolution}  |  Aspect: {aspect_ratio}")
    print(f"  Output:     {output_file}")
    print(f"{'─'*60}")
    print(f"\nPrompt preview (first 300 chars):\n{final_prompt[:300]}...\n")

    start_time = time.time()

    try:
        print("Submitting to Veo API...")
        ref_image_configs = []
        if reference_images:
            ref_image_configs = create_reference_image_configs(reference_images)

        operation = client.models.generate_videos(
            model=model_api_name,
            prompt=final_prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                number_of_videos=1,
                reference_images=ref_image_configs if ref_image_configs else None,
            ),
        )

        print("Waiting for generation to complete ", end="", flush=True)
        while not operation.done:
            time.sleep(poll_interval)
            operation = client.operations.get(operation)
            print(".", end="", flush=True)
        print(" done!")

        generated_videos = operation.response.generated_videos
        if not generated_videos:
            raise RuntimeError("Veo returned no videos — check your API quota and prompt.")

        video_uri = generated_videos[0].video.uri
        video_data = client.files.download(file=video_uri)
        with open(output_file, "wb") as f:
            f.write(video_data)

        wall_time = time.time() - start_time
        size_mb = round(os.path.getsize(output_file) / (1024 * 1024), 2)
        vid_dur = get_video_duration(output_file)
        cost = estimate_cost(model_key, resolution, vid_dur)
        print(f"✓ Saved: {output_file} ({size_mb:.1f} MB) in {wall_time:.0f}s")

        return log_generation(
            scene_id=scene_id,
            model_key=model_key,
            prompt=final_prompt,
            output_file=output_file,
            duration_seconds=wall_time,
            success=True,
            model_api_name=model_api_name,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            file_size_mb=size_mb,
            video_duration_seconds=vid_dur,
            reference_images_count=ref_count,
            retry_count=0,
            estimated_cost_usd=cost,
        )

    except Exception as e:
        wall_time = time.time() - start_time
        print(f"✗ Generation failed: {e}")
        return log_generation(
            scene_id=scene_id,
            model_key=model_key,
            prompt=final_prompt,
            output_file=output_file,
            duration_seconds=wall_time,
            success=False,
            error=str(e),
            error_type=_classify_error(e),
            model_api_name=model_api_name,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            reference_images_count=ref_count,
            retry_count=0,
        )
