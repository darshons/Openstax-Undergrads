import argparse
import os
from pathlib import Path

from .eval import evaluate_clip
from .scenario_loader import load_scenario, get_clip


def load_env():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Transcribe a single generated clip and evaluate it against its scenario.json script."
    )
    parser.add_argument("--video", required=True, help="Path to the clip's video file.")
    parser.add_argument("--scenario", required=True, help="Path to scenario.json.")
    parser.add_argument("--scene-id", type=int, required=True, help="scene_id in scenario.json.")
    parser.add_argument("--clip-id", type=int, required=True, help="clip_id within that scene.")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key for the speaker-attribution judge (or set GEMINI_API_KEY env var).",
    )
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return

    scenario = load_scenario(args.scenario)
    clip = get_clip(scenario, args.scene_id, args.clip_id)

    from google import genai

    client = genai.Client(api_key=args.api_key)

    report = evaluate_clip(
        client=client,
        video_path=args.video,
        scene_id=args.scene_id,
        clip_id=args.clip_id,
        dialogue=clip["dialogue"],
        characters=clip["characters"],
    )

    print(f"\n{'─'*60}")
    print(f"EVAL SUMMARY — scene {args.scene_id}, clip {args.clip_id}")
    print(f"{'─'*60}")
    print(f"Dialogue match : {'PASS' if report['dialogue_match']['passed'] else 'FAIL'} "
          f"(similarity={report['dialogue_match']['similarity']})")
    if report["speaker_attribution"] is None:
        print("Speaker attrib.: SKIPPED (early stop — dialogue match failed)")
    else:
        print(f"Speaker attrib.: {'PASS' if report['speaker_attribution']['attribution_passed'] else 'FAIL'}")
    print(f"Estimated cost : ${report['estimated_cost_usd']}")
    print(f"Overall        : {'PASS' if report['passed'] else 'FAIL'}")
    print(f"\nTranscript: {report['transcript_path']}")
    print(f"Eval report: output/eval_reports/{Path(args.video).stem}_eval.json")


if __name__ == "__main__":
    main()
