import time
from pathlib import Path

from video_generator import veo_api
from video_generator.prompt_builder import build_veo_prompt

from . import logging_utils
from .stitch import stitch_clips

DEFAULT_CLIP_DURATION_SECONDS = 8


def _build_flf_clip_prompt(scene: dict, clip: dict, characters: list, visual_style: str) -> str:
    """Same per-clip field merge as prompt_builder.build_clip_prompts, but
    always is_continuation=False — every FLF clip is independently pinned by
    its own first/last frame images, never chained via video extension, so it
    should never use the extension-chain continuation phrasing."""
    shared_audio = scene.get("audio", {})
    clip_scene = {
        "scene_id": scene.get("scene_id"),
        "setting": clip.get("setting", scene.get("setting", "")),
        "character_actions": clip.get("character_actions", scene.get("character_actions", "")),
        "camera": clip.get("camera") or scene.get("camera", {}),
        "audio": {
            "dialogue": clip.get("dialogue", []),
            "sound_effects": clip.get("sound_effects", shared_audio.get("sound_effects", "none")),
            "ambience": clip.get("ambience", shared_audio.get("ambience", "none")),
        },
    }
    return build_veo_prompt(clip_scene, characters, visual_style, is_continuation=False)


def run_scene_flf(
    client,
    scenario: dict,
    scene_id: int,
    frame_pairs: list,
    output_dir: str,
    duration_seconds: int = DEFAULT_CLIP_DURATION_SECONDS,
) -> dict:
    """
    Generates one Veo clip per entry in frame_pairs (as produced by
    image_gen.generate_clip_frame_images), each anchored by its own pinned
    first and last frame image instead of an extension chain. Downloads and
    logs each clip independently, then — if every clip succeeded — stitches
    them together in order via ffmpeg into one continuous scene video.
    """
    scene = next((s for s in scenario["scenes"] if s["scene_id"] == scene_id), None)
    if scene is None:
        raise ValueError(f"No scene found with id {scene_id}")

    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    clip_lookup = {c["clip_id"]: c for c in scene["clips"]}

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clip_results = []
    total_cost_usd = 0.0
    total_time_seconds = 0.0

    for pair in frame_pairs:
        clip_id = pair["clip_id"]
        clip = clip_lookup[clip_id]
        prompt = _build_flf_clip_prompt(scene, clip, characters, visual_style)

        start = time.time()
        output_file = None
        error = None
        success = False
        retry_count = 0
        cost_usd = None

        try:
            video_obj, attempts, recovered_error = veo_api.generate_flf_clip(
                client,
                prompt,
                first_frame_image=pair["first_frame_path"],
                last_frame_image=pair["last_frame_path"],
                clip_index=clip_id,
                duration_seconds=duration_seconds,
            )
            retry_count = attempts - 1
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = str(out_dir / f"scene{scene_id}_clip{clip_id}_{timestamp}.mp4")
            veo_api.download_video(client, video_obj, output_file)
            cost_usd = veo_api.estimate_cost(veo_api.MODEL_KEY, veo_api.RESOLUTION, duration_seconds)
            success = True
            error = recovered_error
        except Exception as e:
            error = str(e)
        finally:
            elapsed = time.time() - start
            total_time_seconds += elapsed
            if cost_usd:
                total_cost_usd += cost_usd

            logging_utils.log_clip_attempt(
                scene_id=scene_id,
                clip_id=clip_id,
                model_key=veo_api.MODEL_KEY,
                first_frame_image=pair["first_frame_path"],
                last_frame_image=pair["last_frame_path"],
                duration_seconds=duration_seconds,
                success=success,
                cost_usd=cost_usd,
                time_seconds=elapsed,
                output_file=output_file,
                retry_count=retry_count,
                error=error,
            )

        clip_results.append(
            {"clip_id": clip_id, "success": success, "output_file": output_file, "error": error}
        )

    stitched_output_file = None
    stitch_error = None
    if clip_results and all(c["success"] for c in clip_results):
        clip_paths = [c["output_file"] for c in clip_results]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        stitched_path = str(out_dir / f"scene{scene_id}_stitched_{timestamp}.mp4")
        try:
            stitched_output_file = stitch_clips(clip_paths, stitched_path)
        except Exception as e:
            stitch_error = str(e)
    elif clip_results:
        stitch_error = "Skipped stitching — not all clips succeeded."

    return {
        "scene_id": scene_id,
        "clips": clip_results,
        "total_cost_usd": round(total_cost_usd, 4),
        "total_time_seconds": round(total_time_seconds, 1),
        "stitched_output_file": stitched_output_file,
        "stitch_error": stitch_error,
    }
