import sys
import time
from pathlib import Path

# Transcript_Eval_Pipeline is a sibling top-level package under backend/, not
# on a shared import path with Video_Generation_Pipeline — neither is packaged.
_TRANSCRIPT_EVAL_ROOT = Path(__file__).resolve().parents[2] / "Transcript_Eval_Pipeline"
if str(_TRANSCRIPT_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TRANSCRIPT_EVAL_ROOT))

from transcript_eval.video_judge import evaluate_clip  # noqa: E402
from transcript_eval.report_utils import EVAL_REPORT_DIR  # noqa: E402

from .veo_api import download_video, get_video_duration  # noqa: E402


def extract_new_segment(
    cumulative_video_path: str, prev_duration: float, new_duration: float, out_path: str
) -> str:
    """Isolate the newest clip's span out of a cumulative Veo download.

    Veo's extension API returns the full video-so-far on every call, not an
    incremental segment — this trims [prev_duration, new_duration) out of it
    so transcript_eval (built to evaluate one isolated clip) sees only the
    newest clip's audio/video, not everything before it.
    """
    from moviepy import VideoFileClip

    video = VideoFileClip(cumulative_video_path)
    end = min(new_duration, video.duration)
    sub = video.subclipped(prev_duration, end)
    sub.write_videofile(out_path, codec="libx264", audio_codec="aac", logger=None)
    sub.close()
    video.close()
    return out_path


def verify_clip(
    client,
    video_obj,
    prev_duration: float,
    scene_id: int,
    clip_id: int,
    dialogue: list,
    characters: list,
    tmp_dir: Path,
    setting: str = "",
    character_actions: str = "",
) -> tuple:
    """Download the cumulative video, isolate the newest clip, run transcript_eval
    on the isolated clip only (eval still judges just this clip's own audio/visuals,
    not the whole scene-so-far). The isolated clip video is only ever an eval
    input and is always discarded once eval finishes.

    The cumulative video (the whole scene so far, including this clip) is
    discarded if eval passed — but kept on disk if eval failed. A failed clip
    causes the entire scene attempt to be discarded and regenerated from clip 1
    (see _generate_and_verify's ClipEvalFailedError handling), so the isolated
    clip alone wouldn't be useful for review after the fact; the full
    scene-so-far is the artifact worth keeping.

    Returns (report, new_cumulative_duration, kept_cumulative_path_or_None).
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    cumulative_path = tmp_dir / f"scene{scene_id}_clip{clip_id}_cumulative_{ts}.mp4"
    clip_path = tmp_dir / f"scene{scene_id}_clip{clip_id}_{ts}.mp4"

    try:
        download_video(client, video_obj, str(cumulative_path))
        new_duration = get_video_duration(str(cumulative_path))
        extract_new_segment(
            str(cumulative_path), prev_duration, new_duration, str(clip_path)
        )
        report = evaluate_clip(
            client=client,
            video_path=str(clip_path),
            scene_id=scene_id,
            clip_id=clip_id,
            dialogue=dialogue,
            characters=characters,
            setting=setting,
            character_actions=character_actions,
        )
    except Exception:
        cumulative_path.unlink(missing_ok=True)
        raise
    finally:
        clip_path.unlink(missing_ok=True)

    if report["passed"]:
        cumulative_path.unlink(missing_ok=True)
        return report, new_duration, None
    return report, new_duration, str(cumulative_path)


def eval_report_path_for(video_path: str) -> str:
    return str(Path(EVAL_REPORT_DIR) / f"{Path(video_path).stem}_eval.json")


def eval_failure_reason(report: dict) -> str:
    vj = report["video_judge"]
    if vj["status"] == "pass":
        return "unknown eval failure"

    reasons = []
    if vj["visual_issues_found"]:
        reasons.append(f"visual: {vj['visual_notes']}")
    if vj["dialogue_issues_found"]:
        reasons.append(f"dialogue: {vj['dialogue_notes']}")
    if vj["script_alignment_issues_found"]:
        reasons.append(f"script alignment: {vj['script_alignment_notes']}")
    return "; ".join(reasons) if reasons else "video judge flagged an issue"
