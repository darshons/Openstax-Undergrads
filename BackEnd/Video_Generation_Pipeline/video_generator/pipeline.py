import os
import time
from datetime import datetime

from .logging_utils import OUTPUT_DIR, log_generation
from .prompt_builder import build_clip_prompts
from .veo_api import (
    MODEL_KEY,
    RESOLUTION,
    ASPECT_RATIO,
    VALID_FIRST_CLIP_SECONDS,
    EXTENSION_SECONDS,
    MAX_CLIPS,
    EXTENSION_SETTLE_SECONDS,
    generate_first_clip,
    generate_extension_clip,
    download_video,
    get_video_duration,
    estimate_cost,
    _classify_error,
    _VeoExhaustedError,
)


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

    effective_first = 8 if reference_images else first_clip_seconds
    est_seconds = effective_first + (num_clips - 1) * EXTENSION_SECONDS

    print(f"\n{'─'*60}")
    print(f"SCENE {scene_id} — {num_clips} clips (~{est_seconds}s total)")
    print(f"{'─'*60}")

    start_time = time.time()
    total_retries = 0

    video_obj, attempts = generate_first_clip(
        client, clip_prompts[0], clip_index=1,
        reference_images=reference_images, duration_seconds=first_clip_seconds,
    )
    total_retries += attempts - 1

    i = 1
    try:
        for i, prompt in enumerate(clip_prompts[1:], start=2):
            video_obj, attempts = generate_extension_clip(client, prompt, video_obj, clip_index=i)
            total_retries += attempts - 1
            if i < num_clips:
                print(f"  Settling {EXTENSION_SETTLE_SECONDS}s before next hop...")
                time.sleep(EXTENSION_SETTLE_SECONDS)
    except Exception as e:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        completed_clips = i - 1
        checkpoint = str(OUTPUT_DIR / f"scene{scene_id}_checkpoint_clip{completed_clips}_{ts}.mp4")
        download_video(client, video_obj, checkpoint)
        print(f"\n  Extension failed at clip {i}: {e}")
        print(f"  Last good video saved: {checkpoint}")

        # Count retries used by the failing clip (carried on _VeoExhaustedError)
        total_retries += getattr(e, "attempts_used", 1) - 1

        wall_time = time.time() - start_time
        size_mb = round(os.path.getsize(checkpoint) / (1024 * 1024), 2)
        vid_dur = get_video_duration(checkpoint)
        # Fallback: estimate from clip count when moviepy is unavailable
        if vid_dur is None:
            effective_first = 8 if reference_images else first_clip_seconds
            vid_dur = round(effective_first + (completed_clips - 1) * EXTENSION_SECONDS, 1)
        ref_count = len(reference_images) if reference_images else 0
        log_generation(
            scene_id=scene_id,
            model_key=MODEL_KEY,
            prompt="\n\n--- CLIP BREAK ---\n\n".join(clip_prompts),
            output_file=checkpoint,
            duration_seconds=wall_time,
            success=False,
            error=str(e),
            error_type=_classify_error(e),
            resolution=RESOLUTION,
            aspect_ratio=ASPECT_RATIO,
            file_size_mb=size_mb,
            video_duration_seconds=vid_dur,
            reference_images_count=ref_count,
            retry_count=total_retries,
            estimated_cost_usd=estimate_cost(MODEL_KEY, RESOLUTION, vid_dur),
        )
        raise

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sprite_label = "sprites" if reference_images else "no_sprites"
    final_path = str(OUTPUT_DIR / f"scene{scene_id}_final_{sprite_label}_{timestamp}.mp4")
    download_video(client, video_obj, final_path)

    wall_time = time.time() - start_time
    size_mb = round(os.path.getsize(final_path) / (1024 * 1024), 2)
    vid_dur = get_video_duration(final_path)
    ref_count = len(reference_images) if reference_images else 0
    cost = estimate_cost(MODEL_KEY, RESOLUTION, vid_dur)

    log_generation(
        scene_id=scene_id,
        model_key=MODEL_KEY,
        prompt="\n\n--- CLIP BREAK ---\n\n".join(clip_prompts),
        output_file=final_path,
        duration_seconds=wall_time,
        success=True,
        resolution=RESOLUTION,
        aspect_ratio=ASPECT_RATIO,
        file_size_mb=size_mb,
        video_duration_seconds=vid_dur,
        reference_images_count=ref_count,
        retry_count=total_retries,
        estimated_cost_usd=cost,
    )

    print(f"\nScene {scene_id} complete in {wall_time:.0f}s")
    print(f"Final video: {final_path}")
    return final_path


def run_scenario_pipeline(client, scenario: dict, reference_images: list = None) -> list:
    """
    Build clip prompts for every scene and run the stitching pipeline for each.
    Returns a list of result dicts: {scene_id, success, output_file, error}.
    """
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scenes = scenario["scenes"]

    results = []
    for scene in scenes:
        scene_id = scene["scene_id"]
        try:
            clip_prompts = build_clip_prompts(scene, characters, visual_style)
            final_path = run_scene_pipeline(
                client=client,
                scene_id=scene_id,
                clip_prompts=clip_prompts,
                reference_images=reference_images,
            )
            results.append({"scene_id": scene_id, "success": True, "output_file": final_path, "error": None})
        except Exception as e:
            results.append({"scene_id": scene_id, "success": False, "output_file": None, "error": str(e)})

    return results
