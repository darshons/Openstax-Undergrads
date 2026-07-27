import shutil
import subprocess
import tempfile
from pathlib import Path


def stitch_clips(clip_paths: list, output_path: str) -> str:
    """Concatenate clip mp4s (in the given order) into one continuous video via
    ffmpeg's concat demuxer, re-encoding to guarantee compatible timestamps/codecs
    across independently-generated Veo clips (a plain `-c copy` concat can produce
    a broken output if any clip's encoding parameters drift slightly)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`) to stitch clips."
        )
    if not clip_paths:
        raise ValueError("No clips to stitch.")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip_path in clip_paths:
            abs_path = str(Path(clip_path).resolve()).replace("'", "'\\''")
            f.write(f"file '{abs_path}'\n")
        list_file = f.name

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264",
                "-c:a", "aac",
                output_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg stitching failed:\n{result.stderr}")
    finally:
        Path(list_file).unlink(missing_ok=True)

    return output_path
