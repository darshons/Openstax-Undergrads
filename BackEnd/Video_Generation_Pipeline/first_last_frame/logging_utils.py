import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output/first_last_frame")
LOG_FILE = OUTPUT_DIR / "flf_log.json"


def load_log() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(entries: list):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def log_clip_attempt(
    *,
    scene_id: int,
    clip_id: int,
    model_key: str,
    first_frame_image: str,
    last_frame_image: str,
    duration_seconds: float,
    success: bool,
    cost_usd: float = None,
    time_seconds: float,
    output_file: str = None,
    retry_count: int = 0,
    error: str = None,
):
    """One flat entry per clip generated via first+last-frame interpolation.
    No nested scene-attempt/eval structure — this prototype has no eval or
    scene-restart logic."""
    entries = load_log()
    entry = {
        "scene_id": scene_id,
        "clip_id": clip_id,
        "model": model_key,
        "first_frame_image": first_frame_image,
        "last_frame_image": last_frame_image,
        "duration_seconds": duration_seconds,
        "success": success,
        "cost_usd": cost_usd,
        "time_seconds": round(time_seconds, 1),
        "output_file": output_file,
        "retry_count": retry_count,
        "timestamp": datetime.now().isoformat(),
        "error": error,
    }
    entries.append(entry)
    save_log(entries)
    return entry
