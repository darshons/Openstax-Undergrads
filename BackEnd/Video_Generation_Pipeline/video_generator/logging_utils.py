import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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


def log_scene_attempt(
    *,
    scene_id: int,
    scene_attempt: int,
    model_key: str,
    reference_images: list = None,
    success: bool,
    eval_passed: bool = None,
    total_time_seconds: float,
    clips: list,
    fallback_cost_usd: float = None,
    final_output_file: str = None,
    final_video_duration_seconds: float = None,
    final_file_size_mb: float = None,
    retry_count: int = 0,
    error: str = None,
):
    """One entry per scene-attempt — one full pass through run_scene_pipeline's
    scene_attempt loop, whether it ends in success or gets discarded (eval
    failure or a hard generation error). `clips` holds every clip-generation
    attempt made during this scene-attempt (pass, fail, and discarded alike);
    total_cost_usd sums their estimated_cost_usd — both the successful clips
    and any failed/discarded ones — so money spent on a doomed attempt is
    never dropped, the way per-clip cost/duration used to be lost whenever a
    clip *passed* eval (its isolated video was deleted before duration/cost
    could be captured). Falls back to fallback_cost_usd (the whole-video
    estimate) when clips is empty (verify_clips=False). Scoped to this one
    scene-attempt only — not cumulative across retries/reruns."""
    entries = load_log()
    if clips:
        total_cost = round(
            sum(
                c["estimated_cost_usd"]
                for c in clips
                if c["estimated_cost_usd"] is not None
            ),
            4,
        )
    else:
        total_cost = fallback_cost_usd
    entry = {
        "scene_id": scene_id,
        "scene_attempt": scene_attempt,
        "model": model_key,
        "reference_images": reference_images or [],
        "success": success,
        "eval_passed": eval_passed,
        "total_cost_usd": total_cost,
        "total_time_seconds": round(total_time_seconds, 1),
        "final_output_file": final_output_file,
        "final_video_duration_seconds": final_video_duration_seconds,
        "final_file_size_mb": final_file_size_mb,
        "retry_count": retry_count,
        "timestamp": datetime.now().isoformat(),
        "clips": clips,
        "error": error,
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
