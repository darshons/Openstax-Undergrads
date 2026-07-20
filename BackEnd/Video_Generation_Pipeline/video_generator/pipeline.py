import os
import time
from datetime import datetime
from pathlib import Path

from .logging_utils import OUTPUT_DIR, log_generation
from .prompt_builder import build_clip_prompts
from .clip_verification import verify_clip, eval_failure_reason, eval_report_path_for
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
    ClipEvalFailedError,
)


def _log_clip_attempt(scene_id, clip_id, attempt_number, prompt, report, video_path, attempt_wall_time):
    """One generation_log.json entry per clip-generation attempt made under
    --verify-clips (pass or fail) — separate from the existing scene-level
    final/checkpoint entries, so a clip that got regenerated leaves a full
    record of every take, not just the scene's eventual outcome."""
    vid_dur = get_video_duration(video_path) if video_path else None
    size_mb = round(os.path.getsize(video_path) / (1024 * 1024), 2) if video_path else None
    passed = report["passed"]
    log_generation(
        scene_id=scene_id,
        model_key=MODEL_KEY,
        prompt=prompt,
        output_file=video_path,
        duration_seconds=attempt_wall_time,
        success=passed,
        error=None if passed else eval_failure_reason(report),
        error_type=None if passed else "content_eval_failed",
        resolution=RESOLUTION,
        aspect_ratio=ASPECT_RATIO,
        file_size_mb=size_mb,
        video_duration_seconds=vid_dur,
        estimated_cost_usd=estimate_cost(MODEL_KEY, RESOLUTION, vid_dur),
        clip_id=clip_id,
        attempt_number=attempt_number,
        eval_passed=passed,
        eval_report_path=eval_report_path_for(video_path) if video_path else None,
    )


def _generate_and_verify(
    generate_fn,
    clip_id,
    client,
    verify_clips,
    scene_attempt,
    prev_duration,
    scene_id,
    dialogue,
    characters,
    prompt,
):
    """Run generate_fn() — a thunk returning (video_obj, attempts) — and, if
    verify_clips, check the result against transcript_eval before accepting it.

    A failed eval raises ClipEvalFailedError immediately, with no in-place
    retry: Veo's extension feature makes a regenerated clip highly likely to
    fail the same way, so retries happen at the scene level instead —
    run_scene_pipeline catches this and restarts the whole scene from clip 1.
    scene_attempt (1-based) is only used to label this attempt's
    generation_log.json entry.
    Every attempt gets its own generation_log.json entry via
    _log_clip_attempt — a failed attempt's isolated clip video is kept on
    disk (moved out of the temp dir) so the log entry points to something
    reviewable, not just a line of text.

    Returns (video_obj, attempts, new_duration). new_duration == prev_duration
    when verify_clips is False (duration tracking only matters for eval).
    """
    attempt_start = time.time()
    video_obj, attempts = generate_fn()
    if not verify_clips:
        return video_obj, attempts, prev_duration

    report, new_duration, failed_clip_path = verify_clip(
        client,
        video_obj,
        prev_duration,
        scene_id,
        clip_id,
        dialogue,
        characters,
        OUTPUT_DIR / "_clip_eval_tmp",
    )

    # Relocate (not rename) a failed attempt's video: evaluate_clip already
    # saved its eval report keyed on this exact filename's stem, so the
    # stem must survive the move for eval_report_path_for() to resolve —
    # only the directory changes, into a dedicated failed_clips/ folder.
    kept_path = None
    if failed_clip_path:
        failed_dir = OUTPUT_DIR / "failed_clips"
        failed_dir.mkdir(parents=True, exist_ok=True)
        kept_path = str(failed_dir / Path(failed_clip_path).name)
        os.replace(failed_clip_path, kept_path)

    _log_clip_attempt(
        scene_id, clip_id, scene_attempt, prompt, report, kept_path, time.time() - attempt_start
    )

    if report["passed"]:
        return video_obj, attempts, new_duration

    print(f"  Clip {clip_id} failed eval: {eval_failure_reason(report)}")
    if kept_path:
        print(f"  Failed attempt saved: {kept_path}")
    raise ClipEvalFailedError(f"clip {clip_id}: {eval_failure_reason(report)}")


def run_scene_pipeline(
    client,
    scene_id,
    clip_prompts,
    reference_images=None,
    first_clip_seconds=8,
    verify_clips=False,
    eval_retries=1,
    scene=None,
    characters=None,
):
    """
    Generate one scene as a single continuous video via Veo extension.

    clip_prompts: one prompt per clip, in order, built by build_clip_prompts.
    first_clip_seconds: 4/6/8 — only takes effect if reference_images is None.
    verify_clips: if True, transcribe + evaluate each clip against `scene`'s
        dialogue as it's generated. Any clip failing eval immediately abandons
        the scene and regenerates it from clip 1 (Veo's extension feature makes
        a regenerated clip highly likely to fail the same way as its
        predecessor), up to `eval_retries` scene-level regenerations. Requires
        `scene` and `characters` (the raw scenario.json scene dict and
        character list — used to look up each clip's expected dialogue).
    """
    num_clips = len(clip_prompts)
    if num_clips < 1:
        raise ValueError("clip_prompts is empty — nothing to generate.")
    if first_clip_seconds not in VALID_FIRST_CLIP_SECONDS:
        raise ValueError(
            f"first_clip_seconds must be one of {VALID_FIRST_CLIP_SECONDS}."
        )
    if num_clips > MAX_CLIPS:
        raise ValueError(
            f"{num_clips} clips exceeds Veo's extension ceiling of {MAX_CLIPS} "
            f"clips / ~148s. Split this scene before generating."
        )
    if verify_clips and (scene is None or characters is None):
        raise ValueError("verify_clips=True requires both `scene` and `characters`.")

    effective_first = 8 if reference_images else first_clip_seconds
    est_seconds = effective_first + (num_clips - 1) * EXTENSION_SECONDS

    def _clip_dialogue(idx):
        """0-based clip index -> (dialogue, clip_id) from the raw scene dict."""
        clip = scene["clips"][idx]
        return clip.get("dialogue", []), clip.get("clip_id", idx + 1)

    for scene_attempt in range(eval_retries + 1):
        print(f"\n{'─'*60}")
        print(f"SCENE {scene_id} — {num_clips} clips (~{est_seconds}s total)")
        print(f"{'─'*60}")

        start_time = time.time()
        total_retries = 0

        try:
            # Clip 1 is generated outside the inner try/except below (as
            # before verify_clips existed): if it fails, there is no prior
            # successful video to checkpoint, so a non-eval exception should
            # just propagate rather than attempt a checkpoint download. An
            # eval failure (ClipEvalFailedError) is caught further down to
            # trigger a whole-scene regeneration.
            dialogue, clip_id = (_clip_dialogue(0) if verify_clips else (None, 1))
            video_obj, attempts, cum_duration = _generate_and_verify(
                lambda: generate_first_clip(
                    client,
                    clip_prompts[0],
                    clip_index=1,
                    reference_images=reference_images,
                    duration_seconds=first_clip_seconds,
                ),
                clip_id,
                client,
                verify_clips,
                scene_attempt + 1,
                0.0,
                scene_id,
                dialogue,
                characters,
                clip_prompts[0],
            )
            total_retries += attempts - 1

            i = 1
            try:
                for i, prompt in enumerate(clip_prompts[1:], start=2):
                    dialogue, clip_id = (_clip_dialogue(i - 1) if verify_clips else (None, i))
                    video_obj, attempts, cum_duration = _generate_and_verify(
                        lambda: generate_extension_clip(client, prompt, video_obj, clip_index=i),
                        clip_id,
                        client,
                        verify_clips,
                        scene_attempt + 1,
                        cum_duration,
                        scene_id,
                        dialogue,
                        characters,
                        prompt,
                    )
                    total_retries += attempts - 1
                    if i < num_clips:
                        print(f"  Settling {EXTENSION_SETTLE_SECONDS}s before next hop...")
                        time.sleep(EXTENSION_SETTLE_SECONDS)
            except ClipEvalFailedError:
                # No checkpoint for an eval failure — the whole attempt is
                # about to be discarded and regenerated from clip 1.
                raise
            except Exception as e:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                completed_clips = i - 1
                checkpoint = str(
                    OUTPUT_DIR / f"scene{scene_id}_checkpoint_clip{completed_clips}_{ts}.mp4"
                )
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
                    vid_dur = round(
                        effective_first + (completed_clips - 1) * EXTENSION_SECONDS, 1
                    )
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
        except ClipEvalFailedError as e:
            if scene_attempt < eval_retries:
                print(f"\n  Scene {scene_id} failed eval: {e}")
                print(f"  Regenerating scene {scene_id} from clip 1 "
                      f"(attempt {scene_attempt + 2}/{eval_retries + 1})...")
                time.sleep(EXTENSION_SETTLE_SECONDS)
                continue
            raise

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sprite_label = "sprites" if reference_images else "no_sprites"
        final_path = str(
            OUTPUT_DIR / f"scene{scene_id}_final_{sprite_label}_{timestamp}.mp4"
        )
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


def run_scenario_pipeline(
    client,
    scenario: dict,
    reference_images: list = None,
    verify_clips: bool = False,
    eval_retries: int = 1,
) -> list:
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
                verify_clips=verify_clips,
                eval_retries=eval_retries,
                scene=scene,
                characters=characters,
            )
            results.append(
                {
                    "scene_id": scene_id,
                    "success": True,
                    "output_file": final_path,
                    "error": None,
                }
            )
        except Exception as e:
            results.append(
                {
                    "scene_id": scene_id,
                    "success": False,
                    "output_file": None,
                    "error": str(e),
                }
            )

    return results
