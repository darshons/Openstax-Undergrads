import argparse
import json
import os

from video_generator.cli import load_env
from video_generator.scenario_loader import load_scenario

from .generate_images import manifest_path
from .logging_utils import LOG_FILE
from .video_gen import DEFAULT_CLIP_DURATION_SECONDS, run_scene_flf

OUTPUT_DIR = "output/first_last_frame"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Step 2: generate Veo clips from first/last-frame images produced by generate_images.py."
    )
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON file.")
    parser.add_argument("--scene-id", type=int, required=True, help="Scene ID to generate video for.")
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=DEFAULT_CLIP_DURATION_SECONDS,
        choices=(4, 6, 8),
        help="Duration per clip (default: 8, Veo's max for image-to-video).",
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

    manifest_file = manifest_path(args.scene_id)
    if not manifest_file.exists():
        print(
            f"ERROR: No frame manifest found at {manifest_file}. "
            f"Run generate_images.py for scene {args.scene_id} first."
        )
        return

    with open(manifest_file, "r", encoding="utf-8") as f:
        frame_pairs = json.load(f)

    scenario = load_scenario(args.scenario)

    from google import genai

    client = genai.Client(api_key=args.api_key)

    result = run_scene_flf(
        client,
        scenario,
        args.scene_id,
        frame_pairs,
        OUTPUT_DIR,
        duration_seconds=args.duration_seconds,
    )

    print(f"\n{'─'*60}")
    print("FIRST+LAST-FRAME GENERATION SUMMARY")
    print(f"{'─'*60}")
    for clip in result["clips"]:
        status = "✓" if clip["success"] else "✗"
        print(f"  {status} clip {clip['clip_id']} | {clip['output_file'] or clip['error']}")
    print(f"Total cost: ${result['total_cost_usd']:.4f}")
    print(f"Total time: {result['total_time_seconds']:.1f}s")
    if result["stitched_output_file"]:
        print(f"Stitched video: {result['stitched_output_file']}")
    elif result["stitch_error"]:
        print(f"Stitching: {result['stitch_error']}")
    print(f"\nFull log: {LOG_FILE}")


if __name__ == "__main__":
    main()
