# stitch_solo_clips.py
#
# Assembles the independently-generated solo clips (solo_clip_test.py) into
# one scene video. Each solo clip is a full 8s take with only one line of
# dialogue somewhere inside it plus dead air padding before/after, so this
# trims each clip down to its actual speaking span (using the Whisper
# transcript already produced by transcript_eval during generation) before
# concatenating.
#
# Editing choice: hard cuts, no crossfades. This is a naturalistic dialogue
# scene (shot / reverse-shot coverage), not a montage - crossfades read as a
# scene-transition or time-skip in film convention, which is the wrong
# signal here. A straight cut is what real conversation editing uses when
# switching speakers.
#
# Usage:
#   python stitch_solo_clips.py --clips-dir output/solo_clips
#
import argparse
import json
from pathlib import Path

LEAD_PADDING_SECONDS = 0.3
TAIL_PADDING_SECONDS = 1.0

TRANSCRIPT_DIR = Path(__file__).resolve().parent.parent / "Transcript_Eval_Pipeline" / "output" / "transcripts"
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def _speaking_span(clip_path: Path) -> tuple[float, float] | None:
    """Returns (start, end) of the transcribed dialogue within the clip, from
    the Whisper transcript saved alongside evaluation. None if no transcript
    is found (falls back to using the full clip)."""
    transcript_path = TRANSCRIPT_DIR / f"{clip_path.stem}.json"
    if not transcript_path.exists():
        return None
    with open(transcript_path, "r", encoding="utf-8") as f:
        segments = json.load(f)
    if not segments:
        return None
    return segments[0]["start"], segments[-1]["end"]


def build_trimmed_subclips(clip_paths: list):
    from moviepy import VideoFileClip

    subclips = []
    for path in clip_paths:
        video = VideoFileClip(str(path))
        span = _speaking_span(path)
        if span is None:
            print(f"  {path.name}: no transcript found, using full clip ({video.duration:.1f}s)")
            subclips.append(video)
            continue

        start = max(0.0, span[0] - LEAD_PADDING_SECONDS)
        end = min(video.duration, span[1] + TAIL_PADDING_SECONDS)
        print(f"  {path.name}: trimmed {video.duration:.1f}s -> [{start:.1f}s, {end:.1f}s] ({end - start:.1f}s)")
        subclips.append(video.subclipped(start, end))

    return subclips


def stitch(clips_dir: Path, output_path: Path):
    from moviepy import concatenate_videoclips

    clip_paths = sorted(clips_dir.glob("*.mp4"))
    if not clip_paths:
        raise FileNotFoundError(f"No .mp4 files found in {clips_dir}")

    print(f"Stitching {len(clip_paths)} clips in filename order:")
    subclips = build_trimmed_subclips(clip_paths)

    final = concatenate_videoclips(subclips, method="compose")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(str(output_path), codec="libx264", audio_codec="aac")

    for sc in subclips:
        sc.close()
    final.close()

    print(f"\nDone: {output_path} ({final.duration:.1f}s)")


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
