import argparse
import os
from pathlib import Path

from .scenario_loader import load_scenario, get_clip
from .video_judge import evaluate_clip


def load_env():
    """Load .env into os.environ, without clobbering vars already exported in
    the shell — a terminal `export GEMINI_API_KEY=...` should win over a
    stale/blank value sitting in a .env file."""
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Judge a single generated clip against its scenario.json script using Gemini."
    )
    parser.add_argument("--video", required=True, help="Path to the clip's video file.")
    parser.add_argument("--scenario", required=True, help="Path to scenario.json.")
    parser.add_argument(
        "--scene-id", type=int, required=True, help="scene_id in scenario.json."
    )
    parser.add_argument(
        "--clip-id", type=int, required=True, help="clip_id within that scene."
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key for the video judge (or set GEMINI_API_KEY env var).",
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
        setting=clip["setting"],
        character_actions=clip["character_actions"],
    )
    result = report["video_judge"]

    print(f"\n{'─'*60}")
    print(f"VIDEO JUDGE — scene {args.scene_id}, clip {args.clip_id}")
    print(f"{'─'*60}")
    print(f"Status         : {result['status'].upper()} (confidence={result['confidence']})")
    print(f"Visual         : {'ISSUE — ' + result['visual_notes'] if result['visual_issues_found'] else 'ok'}")
    print(f"Dialogue       : {'ISSUE — ' + result['dialogue_notes'] if result['dialogue_issues_found'] else 'ok'}")
    print(f"Script align.  : {'ISSUE — ' + result['script_alignment_notes'] if result['script_alignment_issues_found'] else 'ok'}")
    print(f"Estimated cost : ${report['estimated_cost_usd']}")
    print(f"\nEval report: {report['video_path']}")
    print(f"Report saved under output/eval_reports/{Path(args.video).stem}_eval.json")


if __name__ == "__main__":
    main()
