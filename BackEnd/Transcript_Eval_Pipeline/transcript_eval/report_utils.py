import json
from pathlib import Path

# Anchored to this package's own location, not the caller's CWD — callers
# outside Transcript_Eval_Pipeline (e.g. Video_Generation_Pipeline, run from
# its own directory) must still land here, not in their own output/.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
EVAL_REPORT_DIR = str(_PACKAGE_ROOT / "output" / "eval_reports")


def save_eval_report(video_path: str, report: dict) -> str:
    stem = Path(video_path).stem
    out_path = Path(EVAL_REPORT_DIR) / f"{stem}_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return str(out_path)
