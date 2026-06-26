#!/usr/bin/env python3
"""
Stitch Pipeline
Generates videos using Veo's video extension feature. Each clip continues from the last second
of the previous one.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from video_gen import (
    load_scenario,
    build_veo_prompt,
    init_output_dir,
    log_generation,
    VEO_MODELS,
    OUTPUT_DIR,
)

#SETTINGS
SCENARIO_FILE = "scenario.json"
MODEL = "veo-3.1-generate-preview"
RESOLUTION = "720p"
ASPECT_RATIO = "16:9"
POLL_INTERVAL = 10
REFERENCE_IMAGES = ["maya_reference.png", "carl_reference.png"]
#DURATION CONSTRAINTS
VALID_FIRST_CLIP_SECONDS = (4, 6, 8)
EXTENSION_SECONDS = 7
MAX_CLIPS = 21
#PROCESSING SETTLE - an extension's output isn't extend-eligible the instant the
#operation reports done; let it finish before chaining the next hop
EXTENSION_SETTLE_SECONDS = 15
#TRANSIENT RETRY - Veo's code 13 INTERNAL ("Video generation failed due to an
#internal server issue. Please try again in a few minutes.") is a documented,
#server-side backend/capacity failure, not a problem with the request. It shows
#up most on repeated extension hops. The API's own guidance is to wait and retry,
#so we re-issue the same generate call with exponential backoff instead of
#crashing and discarding the spent hops. RESOURCE_EXHAUSTED (8) and UNAVAILABLE
#(14) are likewise transient and worth retrying.
MAX_GENERATION_RETRIES = 4
RETRY_BASE_DELAY_SECONDS = 30  # backoff: 30s, 60s, 120s, 240s
RETRYABLE_ERROR_CODES = {8, 13, 14}


class _VeoRetryableError(RuntimeError):
    """A transient Veo failure (code 13 INTERNAL / overload) worth retrying."""

#GENERATE FIRST CLIP
def generate_first_clip(client, prompt, clip_index=1, reference_images=None, duration_seconds=8):
    """
    Generates the opening clip for a scene.

    duration_seconds: 4, 6, or 8 - only when no reference images are used. 
    Asset/subject reference images force 8 second duration for veo-3.1-generate-preview, 
    so the value will get overridden in that case.

    Returns the Veo video object.
    """
    from google.genai import types
    from google.genai.types import VideoGenerationReferenceImage, Image as GenaImage

    #build reference image configs if provided
    ref_image_configs = []
    if reference_images:
        for img_path in reference_images:
            with open(img_path, "rb") as f:
                image_bytes = f.read()
            ref_image_configs.append(
                VideoGenerationReferenceImage(
                    image=GenaImage(image_bytes=image_bytes, mime_type="image/png"),
                    reference_type="asset",
                )
            )

    #reference images force 8 seconds on the preview model - that's okay
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
        operation = _poll_until_done(client, operation)
        return operation.response.generated_videos[0].video

    return _generate_with_retry(_attempt, label=f"clip {clip_index}")

#GENERATE EXTENSION CLIP
def generate_extension_clip(client, prompt, previous_video_obj, clip_index):
    """
    Extend the previous Veo video by one ~7s hop. Duration is NOT configurable on
    extension — the API returns a fixed ~7s continuation.

    The Veo API rejects reference_images when video= (extension mode) is also provided —
    the two are mutually exclusive. Character consistency on extension clips is enforced
    through the is_continuation text anchor in build_veo_prompt instead.
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
        operation = _poll_until_done(client, operation)
        return operation.response.generated_videos[0].video

    return _generate_with_retry(_attempt, label=f"clip {clip_index}")

#TRANSIENT FAILURE HANDLING
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


def _generate_with_retry(generate_fn, label):
    """Run a generate+poll thunk, retrying transient code 13 INTERNAL failures
    with exponential backoff. generate_fn must (re)issue the generate_videos call
    and return the polled-to-done video object. On a transient failure we wait and
    re-issue the whole call (a fresh operation), per Veo's 'try again in a few
    minutes' guidance. Non-transient errors (content policy, etc.) propagate
    immediately."""
    last_err = None
    for attempt in range(1, MAX_GENERATION_RETRIES + 1):
        try:
            return generate_fn()
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


#POLLING
def _poll_until_done(client, operation):
    """Poll operation until Veo finishes generating."""
    print("  Waiting for generation ", end="", flush=True)
    while not operation.done:
        time.sleep(POLL_INTERVAL)
        operation = client.operations.get(operation)
        print(".", end="", flush=True)
    print(" done!")

    #done=True does not mean success — Veo sets error on the operation when generation fails
    #(content policy, transient error, etc.) and leaves response=None
    if getattr(operation, "error", None):
        if _is_retryable_operation_error(operation.error):
            #transient backend failure (code 13 INTERNAL etc.) — caller retries with backoff
            raise _VeoRetryableError(f"Veo generation failed (transient): {operation.error}")
        raise RuntimeError(f"Veo generation failed: {operation.error}")
    if not getattr(operation, "response", None) or not getattr(operation.response, "generated_videos", None):
        raise RuntimeError(
            "Veo returned no videos — operation completed but response is empty. "
            "Possible causes: content policy rejection, API quota, or transient generation failure."
        )
    return operation


#DOWNLOAD CLIP
def download_video(client, video_obj, output_file):
    """ Download one Veo video object. Called once, on the final combined
    video — never on intermediate extension handles."""
    video_data = client.files.download(file=video_obj.uri)
    with open(output_file, "wb") as f:
        f.write(video_data)
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  Saved: {output_file} ({size_mb:.1f} MB)")
    return output_file

#ADD CLIP PROMPTS

def build_clip_prompts(scene, characters, visual_style):
    """
    Turn one scene into an ordered list of per-clip prompts (list[str]), one per
    clip. Each prompt carries the shared stage directions (setting, actions,
    camera, sound bed) plus only that clip's dialogue chunk
    """
    clips = scene.get("clips")
    if not clips:
        raise ValueError(f"Scene {scene.get('scene_id')} has no 'clips' to build clips from.")

    shared_audio = scene.get("audio", {})
    prompts = []
    for i, clip in enumerate(clips):
        #camera: use per-clip override if present, otherwise fall back to scene-level and warn
        clip_camera = clip.get("camera")
        if clip_camera is None:
            print(f"  [scene {scene.get('scene_id')} clip {clip.get('clip_id', i+1)}] No per-clip camera — using scene-level camera.")
            clip_camera = scene.get("camera", {})

        #per-clip mini-scene: shared fields, clip overrides where present, this clip's dialogue only
        clip_scene = {
            "scene_id": scene.get("scene_id"),
            "setting": clip.get("setting", scene.get("setting", "")),
            "character_actions": clip.get("character_actions", scene.get("character_actions", "")),
            "camera": clip_camera,
            "audio": {
                "dialogue": clip.get("dialogue", []),
                "sound_effects": clip.get("sound_effects", shared_audio.get("sound_effects", "none")),
                "ambience": clip.get("ambience", shared_audio.get("ambience", "none")),
            },
        }
        #on_screen_text is an "at end" overlay - only the final clip carries it
        if i == len(clips) - 1 and scene.get("on_screen_text"):
            clip_scene["on_screen_text"] = scene["on_screen_text"]

        prompts.append(build_veo_prompt(clip_scene, characters, visual_style, is_continuation=(i > 0)))

    return prompts

#MAIN SCENE PIPELINE
def run_scene_pipeline(client, scene_id, clip_prompts, reference_images=None, first_clip_seconds=8):
    """
    Generate one scene as a single continuous video via Veo extension.

    clip_prompts: one prompt per clip, in order, built by build_clip_prompts.
    first_clip_seconds: 4/6/8 — only takes effect if reference_images is None.
    """
    num_clips = len(clip_prompts)
    if num_clips < 1:
        raise ValueError("clip_prompts is empty — nothing to generate.")
    if first_clip_seconds not in VALID_FIRST_CLIP_SECONDS:
        raise ValueError(f"first_clip_seconds must be one of {VALID_FIRST_CLIP_SECONDS}.")
    if num_clips > MAX_CLIPS:
        raise ValueError(
            f"{num_clips} clips exceeds Veo's extension ceiling of {MAX_CLIPS} "
            f"clips / ~148s. Split this scene before generating."
        )
    
    #reference images pin the opener to 8s, so reflect that in the estimate
    effective_first = 8 if reference_images else first_clip_seconds
    est_seconds = effective_first + (num_clips - 1) * EXTENSION_SECONDS

    print(f"\n{'─'*60}")
    print(f"SCENE {scene_id} — {num_clips} clips (~{est_seconds}s total)")
    print(f"{'─'*60}")

    start_time = time.time()

    video_obj = generate_first_clip(
        client, clip_prompts[0], clip_index=1,
        reference_images=reference_images, duration_seconds=first_clip_seconds,
    )
    
    i = 1
    try:
        for i, prompt in enumerate(clip_prompts[1:], start=2):
            video_obj = generate_extension_clip(client, prompt, video_obj, clip_index=i)
            #don't chain the next hop until this combined output has settled
            if i < num_clips:
                print(f"  Settling {EXTENSION_SETTLE_SECONDS}s before next hop...")
                time.sleep(EXTENSION_SETTLE_SECONDS)
    except Exception as e:
        #download the last good combined video so the spent hops aren't lost
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint = str(OUTPUT_DIR / f"scene{scene_id}_checkpoint_clip{i-1}_{ts}.mp4")
        download_video(client, video_obj, checkpoint)
        print(f"\n  Extension failed at clip {i}: {e}")
        print(f"  Last good video saved: {checkpoint}")
        raise

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sprite_label = "sprites" if reference_images else "no_sprites"
    final_path = str(OUTPUT_DIR / f"scene{scene_id}_final_{sprite_label}_{timestamp}.mp4")
    download_video(client, video_obj, final_path)

    print(f"\nScene {scene_id} complete in {time.time() - start_time:.0f}s")
    print(f"Final video: {final_path}")
    return final_path


#ENTRY POINT
def main():
    from video_gen import load_env
    load_env()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found in .env")
        return

    from google import genai
    client = genai.Client(api_key=api_key)
    init_output_dir()

    scenario = load_scenario(SCENARIO_FILE)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scenes = scenario["scenes"]

    scene = next(s for s in scenes if s["scene_id"] == 3)

    #clip_prompts: one prompt per clip, built from this scene's clips.
    clip_prompts = build_clip_prompts(scene, characters, visual_style)  #<- yours to write

    run_scene_pipeline(
        client=client,
        scene_id=scene["scene_id"],
        clip_prompts=clip_prompts,
        reference_images=REFERENCE_IMAGES,
    )


if __name__ == "__main__":
    main()