"""CLI entry for the Manim branching-video generator.

Usage (from the repo root, venv active):
    python -m BackEnd.Video_Generation_Pipeline.manim_generator.cli \
        --script BackEnd/Script_Generation_Pipeline/_Script_Outputs/output_script_with_decision_points_anthropic_new.json \
        --out output/manim_demo --quality m
"""

import argparse
import os
import time
from pathlib import Path

from .gemini_client import DEFAULT_MODEL
from .pipeline import run_scenario_pipeline
from .script_adapter import load_script


def load_env():
    """Read KEY=VALUE lines from the nearest .env walking up from cwd
    (mirrors video_generator/cli.py, plus the upward walk so the CLI works
    from any subdirectory)."""
    directory = Path.cwd()
    for candidate in [directory, *directory.parents]:
        env_path = candidate / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip("'\""))
            return


def main():
    parser = argparse.ArgumentParser(
        description="Generate branching Manim scenario videos"
    )
    parser.add_argument(
        "--script", required=True, help="Path to the scenario Script JSON"
    )
    parser.add_argument("--out", default="output", help="Output root directory")
    parser.add_argument(
        "--request-id", default=None, help="Run id (default: timestamped)"
    )
    parser.add_argument(
        "--quality",
        default="m",
        choices=["l", "m", "h"],
        help="Manim render quality (l=480p for iteration, h=1080p final)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--no-golden",
        action="store_true",
        help="Skip stitching the correct-path preview video",
    )
    args = parser.parse_args()

    load_env()
    script = load_script(args.script)
    request_id = args.request_id or time.strftime("run_%Y%m%d_%H%M%S")

    manifest = run_scenario_pipeline(
        script,
        request_id=request_id,
        out_root=args.out,
        quality=args.quality,
        model=args.model,
        stitch_golden=not args.no_golden,
    )

    rendered = [s for s in manifest["scenes"] if s["file"]]
    print(f"\n=== {len(rendered)}/{len(manifest['scenes'])} scenes rendered ===")
    for s in manifest["scenes"]:
        print(f"  scene {s['scene_id']} ({s['type']}): {s['file'] or 'FAILED'}")
    if manifest["golden_path_video"]:
        print(
            f"golden path ({'-'.join(map(str, manifest['golden_path']))}): {manifest['golden_path_video']}"
        )
    print(f"manifest: {os.path.join(args.out, request_id, 'manifest.json')}")
    raise SystemExit(0 if len(rendered) == len(manifest["scenes"]) else 1)


if __name__ == "__main__":
    main()
