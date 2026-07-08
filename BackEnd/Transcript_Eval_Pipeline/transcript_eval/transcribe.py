import json
import os
from pathlib import Path

_WHISPER_MODEL = None


def _ensure_ffmpeg_on_path():
    """moviepy bundles its own ffmpeg via imageio-ffmpeg, but whisper shells out
    to a binary literally named `ffmpeg` on PATH — imageio-ffmpeg's binary has a
    platform-suffixed filename, so symlink it to `ffmpeg` in a dir we add to PATH."""
    import shutil
    import tempfile

    import imageio_ffmpeg

    if shutil.which("ffmpeg"):
        return

    bin_dir = Path(tempfile.gettempdir()) / "transcript_eval_ffmpeg"
    bin_dir.mkdir(exist_ok=True)
    link = bin_dir / "ffmpeg"
    if not link.exists():
        link.symlink_to(imageio_ffmpeg.get_ffmpeg_exe())

    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        _ensure_ffmpeg_on_path()
        import whisper

        _WHISPER_MODEL = whisper.load_model("base")
    return _WHISPER_MODEL


def extract_audio(video_path: str, audio_path: str) -> str:
    from moviepy import VideoFileClip

    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, logger=None)
    video.close()
    return audio_path


def transcribe_clip(video_path: str) -> list:
    """Run local Whisper ASR on a single clip video.

    Returns a list of segments relative to the clip's own timeline:
    [{"start": float, "end": float, "text": str}, ...]
    """
    audio_path = str(Path(video_path).with_suffix(".wav"))
    extract_audio(video_path, audio_path)

    model = _get_whisper_model()
    result = model.transcribe(audio_path)

    Path(audio_path).unlink(missing_ok=True)

    return [
        {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]


def save_transcript(video_path: str, segments: list, output_dir: str) -> str:
    stem = Path(video_path).stem
    out_path = Path(output_dir) / f"{stem}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2)
    return str(out_path)
