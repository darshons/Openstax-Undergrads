# stitch_solo_clips.py
#
# Assembles the independently-generated solo clips (solo_clip_test.py) into
# one scene video. Trimming/transcription/concatenation logic now lives in
# video_generator/stitching.py (importable as a proper package module from
# production code); this stays as a thin CLI wrapper around it.
#
# Usage:
#   python stitch_solo_clips.py --clips-dir output/solo_clips
#
import argparse
from pathlib import Path

from video_generator.stitching import build_trimmed_subclips, stitch  # noqa: F401

OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def _default_output_path(clips_dir: Path) -> Path:
    """clips-dir is .../output/<lesson>/raw/<scene> - mirror that into
    .../output/<lesson>/stitched/<scene>.mp4 by default."""
    scene_name = clips_dir.name
    lesson_dir = clips_dir.parent.parent if clips_dir.parent.name == "raw" else clips_dir.parent
    return lesson_dir / "stitched" / f"{scene_name}.mp4"


def main():
    parser = argparse.ArgumentParser(description="Hard-cut stitch solo clips into one scene video.")
    parser.add_argument("--clips-dir", required=True, help="Directory of per-line solo clips to stitch, e.g. output/what_do_you_say_next/raw/scene1")
    parser.add_argument("--output-name", default=None, help="Output filename (default: mirrors clips-dir into <lesson>/stitched/<scene>.mp4).")
    args = parser.parse_args()

    clips_dir = Path(args.clips_dir)
    if args.output_name:
        output_path = OUTPUT_ROOT / args.output_name
    else:
        output_path = _default_output_path(clips_dir)

    stitch(clips_dir, output_path)


if __name__ == "__main__":
    main()
