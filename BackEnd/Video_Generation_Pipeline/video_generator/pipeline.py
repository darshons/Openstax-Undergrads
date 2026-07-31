import os
import time
from datetime import datetime
from pathlib import Path

from .logging_utils import OUTPUT_DIR, log_scene_attempt
from .prompt_builder import build_clip_prompts
from .clip_verification import verify_clip, eval_failure_reason, eval_report_path_for
from .veo_api import (
    MODEL_KEY,
    RESOLUTION,
    VALID_FIRST_CLIP_SECONDS,
    EXTENSION_SECONDS,
    MAX_CLIPS,
    EXTENSION_SETTLE_SECONDS,
    generate_first_clip,
    generate_extension_clip,
    download_video,
    get_video_duration,
    estimate_cost,
    ClipEvalFailedError,
)


def _build_clip_entry(clip_id, attempt_number, prompt, report, prev_duration, new_duration, attempt_wall_time, recovered_error):
    """One clips[] entry per clip-generation attempt made under --verify-clips
    (pass or fail), appended into the scene-attempt's in-memory list rather
    than written immediately — the caller rolls every attempt's cost/duration
    up into the scene-attempt's total when the scene-attempt finishes.

    Uses report["video_path"] (always set by evaluate_clip, pass or fail) for
    eval_report_path, and this clip's own incremental duration
    (new_duration - prev_duration) for duration/cost — not the isolated clip
    video file, which verify_clip deletes once eval passes: relying on that
    file previously meant a passing clip's cost/duration/eval_report_path
    never got recorded at all.

    error prefers the eval failure reason (more specific/actionable) when
    eval failed; otherwise falls back to recovered_error — a transient Veo
    error that got retried past on the way to this successful generation,
    which would otherwise only ever show up in console output."""
    clip_dur = round(new_duration - prev_duration, 2) if new_duration is not None else None
    passed = report["passed"]
    return {
        "clip_id": clip_id,
        "attempt_number": attempt_number,
        "eval_passed": passed,
        "video_duration_seconds": clip_dur,
        "estimated_cost_usd": estimate_cost(MODEL_KEY, RESOLUTION, clip_dur),
        "generation_time": round(attempt_wall_time, 1),
        "eval_report_path": eval_report_path_for(report["video_path"]),
        "error": eval_failure_reason(report) if not passed else recovered_error,
        "prompt": prompt,
    }


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
    clip_duration_hint,
    clip_log_entries,
):
    """Run generate_fn() — a thunk returning (video_obj, attempts, recovered_error)
    — and, if verify_clips, check the result against transcript_eval before
    accepting it.

    A failed eval raises ClipEvalFailedError immediately, with no in-place
    retry: Veo's extension feature makes a regenerated clip highly likely to
    fail the same way, so retries happen at the scene level instead —
    run_scene_pipeline catches this and restarts the whole scene from clip 1.
    scene_attempt (1-based) is only used to label this attempt's clip entry.

    Every attempt appends its own entry into clip_log_entries (the caller's
    in-memory list for this scene-attempt, rolled up into one
    generation_log.json entry once the scene-attempt finishes) — including a
    generate_fn() failure itself (e.g. Veo exhausts retries) before eval ever
    runs, so no attempt's cost/outcome is silently dropped. A failed eval's
    isolated clip video is kept on disk (moved out of the temp dir) so the
    entry's eval_report_path points at something reviewable, not just a line
    of text.

    Returns (video_obj, attempts, new_duration). new_duration == prev_duration
    when verify_clips is False (duration tracking only matters for eval).

    clip_duration_hint: Veo's expected length for this clip (first_clip_seconds,
    or EXTENSION_SECONDS for a hop) — used to log video_duration_seconds/
    estimated_cost_usd when verify_clips is False, since no video gets
    downloaded (and so no measured duration exists) until the scene finishes.
    """
    attempt_start = time.time()
    try:
        video_obj, attempts, recovered_error = generate_fn()
    except Exception as e:
        clip_log_entries.append({
            "clip_id": clip_id,
            "attempt_number": scene_attempt,
            "eval_passed": None,
            "video_duration_seconds": None,
            "estimated_cost_usd": None,
            "generation_time": round(time.time() - attempt_start, 1),
            "eval_report_path": None,
            "error": str(e),
            "prompt": prompt,
        })
        raise

    if not verify_clips:
        clip_log_entries.append({
            "clip_id": clip_id,
            "attempt_number": scene_attempt,
            "eval_passed": None,
            "video_duration_seconds": clip_duration_hint,
            "estimated_cost_usd": estimate_cost(MODEL_KEY, RESOLUTION, clip_duration_hint),
            "generation_time": round(time.time() - attempt_start, 1),
            "eval_report_path": None,
            "error": recovered_error,
            "prompt": prompt,
        })
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

    clip_log_entries.append(
        _build_clip_entry(
            clip_id, scene_attempt, prompt, report, prev_duration, new_duration,
            time.time() - attempt_start, recovered_error,
        )
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
        clip_log_entries = []

        try:
            # Clip 1 is generated outside the inner try/except below (as
            # before verify_clips existed): if it fails, there is no prior
            # successful video to checkpoint, so a non-eval exception should
            # just propagate rather than attempt a checkpoint download. An
            # eval failure (ClipEvalFailedError) is caught further down to
            # trigger a whole-scene regeneration.
            dialogue, clip_id = _clip_dialogue(0) if verify_clips else (None, 1)
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
                effective_first,
                clip_log_entries,
            )
            total_retries += attempts - 1

            # Veo needs the same processing settle between clip 1 and its
            # first extension as it does between later hops — this used to
            # only happen from clip 2 onward.
            if num_clips > 1:
                print(f"  Settling {EXTENSION_SETTLE_SECONDS}s before next hop...")
                time.sleep(EXTENSION_SETTLE_SECONDS)

            i = 1
            try:
                for i, prompt in enumerate(clip_prompts[1:], start=2):
                    dialogue, clip_id = (
                        _clip_dialogue(i - 1) if verify_clips else (None, i)
                    )
                    video_obj, attempts, cum_duration = _generate_and_verify(
                        lambda: generate_extension_clip(
                            client, prompt, video_obj, clip_index=i
                        ),
                        clip_id,
                        client,
                        verify_clips,
                        scene_attempt + 1,
                        cum_duration,
                        scene_id,
                        dialogue,
                        characters,
                        prompt,
                        EXTENSION_SECONDS,
                        clip_log_entries,
                    )
                    total_retries += attempts - 1
                    if i < num_clips:
                        print(
                            f"  Settling {EXTENSION_SETTLE_SECONDS}s before next hop..."
                        )
                        time.sleep(EXTENSION_SETTLE_SECONDS)
            except ClipEvalFailedError:
                # No checkpoint for an eval failure — the whole attempt is
                # about to be discarded and regenerated from clip 1.
                raise
            except Exception as e:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                completed_clips = i - 1
                checkpoint = str(
                    OUTPUT_DIR
                    / f"scene{scene_id}_checkpoint_clip{completed_clips}_{ts}.mp4"
                )
                print(f"\n  Extension failed at clip {i}: {e}")

                # Checkpoint save is itself a network call and can fail for the same
                # reason the clip generation just did (e.g. a connection timeout) —
                # if it does, still log this scene-attempt with what's known rather
                # than letting the secondary failure propagate uncaught and silently
                # skip log_scene_attempt entirely.
                size_mb = None
                vid_dur = None
                try:
                    download_video(client, video_obj, checkpoint)
                    print(f"  Last good video saved: {checkpoint}")
                    size_mb = round(os.path.getsize(checkpoint) / (1024 * 1024), 2)
                    vid_dur = get_video_duration(checkpoint)
                except Exception as checkpoint_err:
                    checkpoint = None
                    print(f"  Checkpoint save also failed: {checkpoint_err}")
                # Fallback: estimate from clip count when moviepy is unavailable, or
                # the checkpoint download itself failed
                if vid_dur is None:
                    effective_first = 8 if reference_images else first_clip_seconds
                    vid_dur = round(
                        effective_first + (completed_clips - 1) * EXTENSION_SECONDS, 1
                    )

                # Count retries used by the failing clip (carried on _VeoExhaustedError)
                total_retries += getattr(e, "attempts_used", 1) - 1

                wall_time = time.time() - start_time
                log_scene_attempt(
                    scene_id=scene_id,
                    scene_attempt=scene_attempt + 1,
                    model_key=MODEL_KEY,
                    reference_images=reference_images,
                    success=False,
                    eval_passed=None,
                    total_time_seconds=wall_time,
                    clips=clip_log_entries,
                    fallback_cost_usd=estimate_cost(MODEL_KEY, RESOLUTION, vid_dur),
                    final_output_file=checkpoint,
                    final_video_duration_seconds=vid_dur,
                    final_file_size_mb=size_mb,
                    retry_count=total_retries,
                    error=str(e),
                )
                raise
        except ClipEvalFailedError as e:
            log_scene_attempt(
                scene_id=scene_id,
                scene_attempt=scene_attempt + 1,
                model_key=MODEL_KEY,
                reference_images=reference_images,
                success=False,
                eval_passed=False,
                total_time_seconds=time.time() - start_time,
                clips=clip_log_entries,
                retry_count=total_retries,
                error=str(e),
            )
            if scene_attempt < eval_retries:
                print(f"\n  Scene {scene_id} failed eval: {e}")
                print(
                    f"  Regenerating scene {scene_id} from clip 1 "
                    f"(attempt {scene_attempt + 2}/{eval_retries + 1})..."
                )
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
        cost = estimate_cost(MODEL_KEY, RESOLUTION, vid_dur)

        log_scene_attempt(
            scene_id=scene_id,
            scene_attempt=scene_attempt + 1,
            model_key=MODEL_KEY,
            reference_images=reference_images,
            success=True,
            eval_passed=True if verify_clips else None,
            total_time_seconds=wall_time,
            clips=clip_log_entries,
            fallback_cost_usd=cost,
            final_output_file=final_path,
            final_video_duration_seconds=vid_dur,
            final_file_size_mb=size_mb,
            retry_count=total_retries,
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
    on_scene_complete=None,
) -> list:
    """
    Build clip prompts for every scene and run the stitching pipeline for each.
    Returns a list of result dicts: {scene_id, success, output_file, error}.

    on_scene_complete: optional callback invoked with each scene's result dict
    right after it finishes (success or failure) — lets a caller (e.g. an async
    API job) report per-scene progress without waiting on the full scenario.
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
            result = {
                "scene_id": scene_id,
                "success": True,
                "output_file": final_path,
                "error": None,
            }
        except Exception as e:
            result = {
                "scene_id": scene_id,
                "success": False,
                "output_file": None,
                "error": str(e),
            }

        results.append(result)
        if on_scene_complete:
            on_scene_complete(result)

    return results
