import argparse
import json
import os
from pathlib import Path

from video_generator.cli import load_env
from video_generator.scenario_loader import load_scenario

from .image_gen import generate_clip_frame_images

IMAGES_DIR = Path("output/first_last_frame/images")


def manifest_path(scene_id: int) -> Path:
    return IMAGES_DIR / f"scene{scene_id}_frame_manifest.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Step 1: generate first/last-frame images for each clip in a scene."
    )
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON file.")
    parser.add_argument("--scene-id", type=int, required=True, help="Scene ID to generate frames for.")
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

    from google import genai

    client = genai.Client(api_key=args.api_key)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    frame_pairs = generate_clip_frame_images(client, scenario, args.scene_id, str(IMAGES_DIR))

    out_path = manifest_path(args.scene_id)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(frame_pairs, f, indent=2)

    print(f"\nGenerated {len(frame_pairs)} first/last-frame pairs for scene {args.scene_id}.")
    print(f"Manifest: {out_path}")


if __name__ == "__main__":
    main()
