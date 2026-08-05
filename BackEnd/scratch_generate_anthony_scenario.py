import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv("backend.env")
from google import genai

from Video_Generation_Pipeline.video_generator.solo_clip_pipeline import run_scenario_pipeline_solo_clip

SCRIPT_PATH = "Video_Generation_Pipeline/anthony_scenario_script_with_clips.json"
REF_IMAGES_DIR = Path("Video_Generation_Pipeline/reference_images_anthony")
OUTPUT_DIR = Path("Video_Generation_Pipeline/output/anthony_scenario")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the Anthony (Elena's Knee) scenario, one scene at a time.")
    parser.add_argument("--scene-id", type=int, default=None, help="Generate only this scene (default: all scenes).")
    parser.add_argument("--model", default="veo-3.1-fast-generate-preview")
    return parser.parse_args()


def main():
    args = parse_args()

    with open(SCRIPT_PATH) as f:
        scenario = json.load(f)

    if args.scene_id is not None:
        scenario = {**scenario, "scenes": [s for s in scenario["scenes"] if s["scene_id"] == args.scene_id]}
        if not scenario["scenes"]:
            print(f"ERROR: no scene with scene_id={args.scene_id}")
            sys.exit(1)

    character_image_file_mapping = {
        c["character_id"]: str(REF_IMAGES_DIR / f"{c['character_id']}.png")
        for c in scenario["characters"]
    }
    background_image_path = str(REF_IMAGES_DIR / "background_reference_image.png")

    api_key = os.environ["GOOGLE_API_KEY"]
    client = genai.Client(api_key=api_key)

    def on_scene_complete(result):
        if result["success"]:
            print(f"  scene {result['scene_id']} DONE -> {result['output_file']}")
        else:
            print(f"  scene {result['scene_id']} FAILED: {result['error']}")

    print(f"Generating {len(scenario['scenes'])} scene(s) (solo-clip, {args.model})...")
    results = run_scenario_pipeline_solo_clip(
        client=client,
        scenario=scenario,
        character_image_file_mapping=character_image_file_mapping,
        background_image_path=background_image_path,
        output_dir=OUTPUT_DIR,
        model=args.model,
        on_scene_complete=on_scene_complete,
    )

    print("\nFINAL RESULTS:")
    print(json.dumps(results, indent=2))

    failed = [r for r in results if not r["success"]]
    if failed:
        print(f"\n{len(failed)} scene(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
