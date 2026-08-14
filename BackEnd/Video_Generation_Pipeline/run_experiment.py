# run_experiment.py - run the same scenario through the pipeline multiple
# times in a row, with every knob that varies between experiments collected
# here in one place. Each experiment group gets its own timestamped folder
# under output/experiments/ — videos, failed_clips, eval_reports, and
# generation_log.json for every repeat all live together directly in that
# one folder (filenames/log entries are already timestamped per-repeat, so
# nothing collides).
from datetime import datetime
from pathlib import Path

from video_generator.cli import load_env
from video_generator.scenario_loader import load_scenario
from video_generator import pipeline, veo_api, logging_utils, clip_verification

import transcript_eval.report_utils as report_utils_module

# ── EXPERIMENT CONFIG ────────────────────────────────────────────────────
EXPERIMENT_NAME = "my_experiment"
SCENARIO_PATH = "scenario.json"
SCENE_ID = 1  # None = all scenes, or an int to run just one scene
MODEL_KEY = "veo-3.1-fast"  # must be a key in veo_api.VEO_MODELS
REFERENCE_IMAGES = veo_api.REFERENCE_IMAGES  # list of image paths, or []
VERIFY_CLIPS = True
EVAL_RETRIES = 1
NUM_EXPERIMENTS = 5  # how many times to repeat the whole run
# ──────────────────────────────────────────────────────────────────────────

EXPERIMENTS_ROOT = Path("output/experiments")


def configure_paths(experiment_dir):
    experiment_dir.mkdir(parents=True, exist_ok=True)

    pipeline.OUTPUT_DIR = experiment_dir
    logging_utils.LOG_FILE = experiment_dir / "generation_log.json"
    veo_api.MODEL = veo_api.VEO_MODELS[MODEL_KEY]
    veo_api.MODEL_KEY = MODEL_KEY
    pipeline.MODEL_KEY = MODEL_KEY
    report_utils_module.EVAL_REPORT_DIR = str(experiment_dir / "eval_reports")
    clip_verification.EVAL_REPORT_DIR = report_utils_module.EVAL_REPORT_DIR


def run_one(client, scenario, scenes):
    filtered_scenario = {**scenario, "scenes": scenes}
    return pipeline.run_scenario_pipeline(
        client=client,
        scenario=filtered_scenario,
        reference_images=REFERENCE_IMAGES or None,
        verify_clips=VERIFY_CLIPS,
        eval_retries=EVAL_RETRIES,
    )


def main():
    load_env()
    import os

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No Gemini API key. Set GEMINI_API_KEY.")
        return

    scenario = load_scenario(SCENARIO_PATH)
    scenes = scenario["scenes"]
    if SCENE_ID is not None:
        scenes = [s for s in scenes if s["scene_id"] == SCENE_ID]
        if not scenes:
            print(f"ERROR: No scene found with id {SCENE_ID}")
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_dir = EXPERIMENTS_ROOT / f"{EXPERIMENT_NAME}_{timestamp}"

    from google import genai

    client = genai.Client(api_key=api_key)

    configure_paths(experiment_dir)

    all_results = []
    for n in range(1, NUM_EXPERIMENTS + 1):
        print(
            f"\n{'#'*60}\nEXPERIMENT {EXPERIMENT_NAME} — run {n}/{NUM_EXPERIMENTS}\n{'#'*60}"
        )
        results = run_one(client, scenario, scenes)
        all_results.append(results)

    log_entries = logging_utils.load_log()
    total_cost = sum(
        e["total_cost_usd"] for e in log_entries if e.get("total_cost_usd") is not None
    )
    total_retries = sum(e.get("retry_count", 0) for e in log_entries)

    print(f"\n{'─'*60}")
    print("EXPERIMENT SUMMARY")
    print(f"{'─'*60}")
    print(f"Folder: {experiment_dir}")
    for n, results in enumerate(all_results, start=1):
        succeeded = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        print(f"  run{n}: {len(succeeded)} succeeded, {len(failed)} failed")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Total retry attempts: {total_retries}")


if __name__ == "__main__":
    main()
