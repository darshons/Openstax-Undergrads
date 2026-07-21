import json
from datetime import datetime
from pathlib import Path

from .match_dialogue import match_dialogue
from .judge_speaker import judge_speakers
from .transcribe import transcribe_clip, save_transcript

# Anchored to this package's own location, not the caller's CWD — callers
# outside Transcript_Eval_Pipeline (e.g. Video_Generation_Pipeline, run from
# its own directory) must still land here, not in their own output/.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = str(_PACKAGE_ROOT / "output" / "transcripts")
EVAL_REPORT_DIR = str(_PACKAGE_ROOT / "output" / "eval_reports")


def evaluate_clip(
    client,
    video_path: str,
    scene_id: int,
    clip_id: int,
    dialogue: list,
    characters: list,
) -> dict:
    """Run Stage 1 -> 2 -> (3 if not early-stopped) -> aggregate report for one clip."""
    segments = transcribe_clip(video_path)
    transcript_path = save_transcript(video_path, segments, TRANSCRIPT_DIR)

    dialogue_match = match_dialogue(dialogue, segments)

    speaker_attribution = None
    if dialogue_match["passed"]:
        speaker_attribution = judge_speakers(
            client, video_path, segments, dialogue, characters
        )

    overall_passed = dialogue_match["passed"] and (
        speaker_attribution is not None and speaker_attribution["attribution_passed"]
    )

    report = {
        "timestamp": datetime.now().isoformat(),
        "scene_id": scene_id,
        "clip_id": clip_id,
        "video_path": video_path,
        "transcript_path": transcript_path,
        "dialogue_match": dialogue_match,
        "speaker_attribution": speaker_attribution,
        "speaker_attribution_skipped_reason": (
            None if dialogue_match["passed"] else "early_stop: dialogue_match failed"
        ),
        "estimated_cost_usd": (speaker_attribution or {}).get(
            "estimated_cost_usd", 0.0
        ),
        "passed": overall_passed,
    }

    save_eval_report(video_path, report)
    return report


def save_eval_report(video_path: str, report: dict) -> str:
    stem = Path(video_path).stem
    out_path = Path(EVAL_REPORT_DIR) / f"{stem}_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return str(out_path)
