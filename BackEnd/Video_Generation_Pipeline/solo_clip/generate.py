import argparse
import os
from pathlib import Path

from video_generator.cli import load_env
from video_generator.scenario_loader import load_scenario

from .pipeline import run_scenario_pipeline_solo_clip
from .reference_images import ensure_reference_images

OUTPUT_DIR = Path("output/solo_clip")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a scenario using the solo-clip technique: one "
        "isolated clip per speaking character per dialogue line, stitched "
        "together per scene."
    )
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON file.")
    parser.add_argument(
        "--scene-id",
        type=int,
        default=None,
        help="Scene ID to generate. Omit to generate all scenes.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default Veo model (module default in video_generator/veo_api.py otherwise).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key (or set GEMINI_API_KEY env var).",
    )
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return

    scenario = load_scenario(args.scenario)
    scenes = scenario["scenes"]

    if args.scene_id is not None:
        scenes = [s for s in scenes if s["scene_id"] == args.scene_id]
        if not scenes:
            print(f"ERROR: No scene found with id {args.scene_id}")
            return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    from google import genai

    client = genai.Client(api_key=args.api_key)

    filtered_scenario = {**scenario, "scenes": scenes}

    ref_dir = OUTPUT_DIR / "reference_images"
    images = ensure_reference_images(filtered_scenario, ref_dir)
    background_image_path = images.pop("background")

    results = run_scenario_pipeline_solo_clip(
        client=client,
        scenario=filtered_scenario,
        character_image_file_mapping=images,
        background_image_path=background_image_path,
        output_dir=OUTPUT_DIR,
        model=args.model,
    )

    print(f"\n{'─'*60}")
    print("GENERATION SUMMARY")
    print(f"{'─'*60}")
    succeeded = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    print(f"✓ Succeeded: {len(succeeded)}")
    print(f"✗ Failed:    {len(failed)}")
    for r in succeeded:
        print(f"  scene{r['scene_id']} | {r['output_file']}")
    for r in failed:
        print(f"  scene{r['scene_id']} | ERROR: {r['error']}")


if __name__ == "__main__":
    main()
