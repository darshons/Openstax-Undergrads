import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")
LOG_FILE = OUTPUT_DIR / "generation_log.json"


def load_log() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(entries: list):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def save_prompt(prompt: str, output_file: str) -> str:
    prompt_file = Path(output_file).with_suffix(".txt")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    return str(prompt_file)


def log_generation(
    scene_id: int,
    model_key: str,
    prompt: str,
    output_file: str,
    duration_seconds: float,
    success: bool,
    error: str = None,
    model_api_name: str = None,
    resolution: str = None,
    aspect_ratio: str = None,
    file_size_mb: float = None,
    video_duration_seconds: float = None,
    reference_images_count: int = None,
    retry_count: int = None,
    estimated_cost_usd: float = None,
    error_type: str = None,
):
    entries = load_log()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "scene_id": scene_id,
        "model": model_key,
        "model_api_name": model_api_name or model_key,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "prompt": prompt,
        "prompt_char_count": len(prompt) if prompt else None,
        "reference_images_count": reference_images_count,
        "output_file": output_file,
        "file_size_mb": file_size_mb,
        "video_duration_seconds": video_duration_seconds,
        "generation_time": round(duration_seconds, 1),
        "retry_count": retry_count,
        "estimated_cost_usd": estimated_cost_usd,
        "success": success,
        "error": error,
        "error_type": error_type,
    }
    entries.append(entry)
    save_log(entries)
    return entry


def save_checkpoint_metadata(
    scene_id: int, clip_index: int, checkpoint_file: str, error: Exception
):
    entries = load_log()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "scene_id": scene_id,
        "type": "checkpoint",
        "clips_completed": clip_index - 1,
        "checkpoint_file": checkpoint_file,
        "error": str(error),
    }
    entries.append(entry)
    save_log(entries)
    return entry
