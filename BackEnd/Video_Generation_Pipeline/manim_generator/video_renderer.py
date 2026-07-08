"""Render generated Manim scene code and assemble clips.

Core render/snapshot/stitch logic ported from the TheoremExplainAgent OpenStax
fork (src/core/video_renderer.py), reshaped:
- the render->repair retry loop lives in pipeline.py, not here;
- manim is invoked as `sys.executable -m manim` so the venv that runs the
  pipeline is always the one that renders (TEA's bare `manim` broke whenever
  another manim was first on PATH);
- error logs are truncated to their tail before being fed to the repair LLM
  (RITL, ManimBench): the last lines carry the actual exception, the rest is
  noise that dilutes the prompt.
"""

import os
import re
import subprocess
import sys

import cv2
import ffmpeg
from PIL import Image

QUALITY_DIRS = {"h": "1080p60", "m": "720p30", "l": "480p15"}
ERROR_LOG_TAIL_LINES = 12


def truncate_error_log(stderr: str, max_lines: int = ERROR_LOG_TAIL_LINES) -> str:
    """Keep the tail of a manim error dump — the exception and the frames
    nearest to it. Long renders emit hundreds of lines of progress noise."""
    lines = [l for l in stderr.strip().splitlines() if l.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "(...log truncated...)\n" + "\n".join(lines[-max_lines:])


def extract_failing_line(stderr: str, code_filename: str) -> int | None:
    """Pull the line number of the deepest traceback frame that points into
    the generated scene file. Used by the ScopeRefine repair to fix at line
    scope first."""
    line_no = None
    for match in re.finditer(r'File "([^"]+)", line (\d+)', stderr):
        if os.path.basename(match.group(1)) == os.path.basename(code_filename):
            line_no = int(match.group(2))
    return line_no


class VideoRenderer:
    def __init__(self, quality: str = "h"):
        if quality not in QUALITY_DIRS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_DIRS)}")
        self.quality = quality

    def render(self, code_path: str, media_dir: str, scene_name: str | None = None) -> tuple[bool, str]:
        """Render one scene file. Returns (success, stderr). Runs with
        cwd=the code file's directory so `from assets import *`,
        `from kokoro_voiceover import KokoroService` and the local manim.cfg
        all resolve. `scene_name` must be passed when the file defines more
        than one Scene class (manim would prompt interactively otherwise)."""
        code_dir = os.path.dirname(os.path.abspath(code_path))
        cmd = [
            sys.executable, "-m", "manim",
            f"-q{self.quality}",
            os.path.basename(code_path),
        ]
        if scene_name:
            cmd.append(scene_name)
        cmd += ["--media_dir", os.path.abspath(media_dir), "--progress_bar", "none"]
        result = subprocess.run(cmd, cwd=code_dir, capture_output=True, text=True)
        return result.returncode == 0, result.stderr

    def find_scene_video(self, media_dir: str, code_path: str) -> str | None:
        """Locate the mp4 manim produced for a code file."""
        stem = os.path.splitext(os.path.basename(code_path))[0]
        video_dir = os.path.join(media_dir, "videos", stem, QUALITY_DIRS[self.quality])
        if not os.path.isdir(video_dir):
            return None
        mp4s = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
        if not mp4s:
            return None
        return os.path.join(video_dir, mp4s[0])

    def snapshot(self, video_path: str, output_path: str, sample_every_s: float = 2.0) -> Image.Image:
        """Save + return the sampled frame with the most non-background pixels
        (the 'busiest' frame) — the most informative single frame for the
        layout critic."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(fps * sample_every_s))
        best, best_score, idx = None, -1, 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # score = pixels that differ from the frame's dominant flat background
                score = int((cv2.absdiff(gray, int(gray.mean())) > 24).sum())
                if score > best_score:
                    best_score, best = score, frame
            idx += 1
        cap.release()
        if best is None:
            raise FileNotFoundError(f"No readable frames in {video_path}")
        image = Image.fromarray(cv2.cvtColor(best, cv2.COLOR_BGR2RGB))
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        image.save(output_path)
        return image

    def probe_duration(self, video_path: str) -> float | None:
        try:
            probe = ffmpeg.probe(video_path)
            return float(probe["format"]["duration"])
        except Exception:
            return None

    def stitch(self, video_paths: list[str], output_path: str):
        """Concatenate clips into one mp4 (the golden-path preview). Clips
        without an audio stream get silent audio so the concat filter accepts
        a uniform stream layout."""
        streams = []
        for video in video_paths:
            probe = ffmpeg.probe(video)
            has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
            input_vid = ffmpeg.input(video)
            if has_audio:
                streams.extend([input_vid["v"], input_vid["a"]])
            else:
                duration = float(probe["format"]["duration"])
                silent = ffmpeg.input(
                    "anullsrc=channel_layout=stereo:sample_rate=44100", f="lavfi", t=duration
                )["a"]
                streams.extend([input_vid["v"], silent])

        (
            ffmpeg.concat(*streams, v=1, a=1, unsafe=True)
            .output(
                output_path,
                **{"c:v": "libx264", "c:a": "aac", "preset": "veryfast", "crf": "26",
                   "movflags": "+faststart"},
            )
            .overwrite_output()
            .run(quiet=True)
        )
        return output_path
