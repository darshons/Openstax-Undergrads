# Assembles independently-generated solo clips (one isolated clip per
# dialogue line - see solo_clip/pipeline.py) into one scene video. Each solo
# clip is a full 8s take with only one line of dialogue somewhere inside it
# plus dead air padding before/after, so this trims each clip down to its
# actual speaking span before concatenating.
#
# Transcribes each clip fresh at stitch time rather than caching to a shared
# location - a shared cache keyed by bare filename collides across scenes
# whose clips happen to share a name (e.g. every scene's clip 1), which
# silently produces wrong trim points. Re-transcribing per clip is cheap (a
# few seconds, local Whisper) and immune to that collision entirely.
#
# Editing choice: hard cuts, no crossfades. This is a naturalistic dialogue
# scene (shot / reverse-shot coverage), not a montage - crossfades read as a
# scene-transition or time-skip in film convention, which is the wrong
# signal here. A straight cut is what real conversation editing uses when
# switching speakers.
#
# The trim points above (start/end of the speaking span) land at arbitrary
# waveform samples, not zero-crossings, so both the trim itself and the
# splice between clips leave an audible click - a waveform discontinuity,
# not a Veo artifact. A short audio-only declick fade at each subclip's
# edges removes it without functioning as a perceptible crossfade (unlike
# the video track, which stays a true hard cut).
from pathlib import Path

LEAD_PADDING_SECONDS = 0.3
TAIL_PADDING_SECONDS = 1.0
DECLICK_FADE_SECONDS = 0.03


def _words(text: str) -> set:
    import re

    return set(re.findall(r"[a-z']+", text.lower()))


def _expected_text_for(clip_path: Path) -> str | None:
    """A sidecar <clip_stem>.txt next to the clip, written by
    solo_clip/pipeline.py at generation time, records the exact line this
    clip was generated for. Older clips generated before this existed have
    no sidecar - callers fall back to the pre-existing behavior for those."""
    sidecar = clip_path.with_suffix(".txt")
    if not sidecar.exists():
        return None
    return sidecar.read_text(encoding="utf-8").strip()


def _speaking_span(clip_path: Path) -> tuple[float, float] | None:
    """Returns (start, end) of the spoken dialogue within the clip, by
    transcribing it directly. None if no speech is detected (silent gesture
    clips, or a transcription miss - falls back to using the full clip).

    Veo occasionally tacks on a stray unscripted interjection (e.g. a filler
    "Oh." before or after the actual line) that Whisper picks up as its own
    segment. Blindly spanning first-detected-speech to last-detected-speech
    then includes that interjection in the final cut. When a sidecar records
    the expected line, segments that share no words with it are dropped
    before computing the span - a stray "Oh." has zero overlap with a real
    scripted line, while a legitimately short line (e.g. "Hi.") still
    matches itself. Falls back to the full span if nothing matches (or if
    there's no sidecar to compare against), so this only ever narrows the
    span, never breaks on a transcription miss."""
    from moviepy import VideoFileClip

    if VideoFileClip(str(clip_path)).audio is None:
        return None

    from .transcribe import transcribe_clip

    segments = transcribe_clip(str(clip_path))
    if not segments:
        return None

    expected = _expected_text_for(clip_path)
    if expected:
        expected_words = _words(expected)
        matched = [s for s in segments if _words(s["text"]) & expected_words]
        if matched:
            segments = matched

    return segments[0]["start"], segments[-1]["end"]


def _declicked(video):
    """Short audio-only fade at both edges so a hard trim/splice point lands
    on near-silence instead of an arbitrary waveform sample - see module
    docstring. Video track is untouched; only long enough to kill the click,
    not long enough to read as a crossfade."""
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut

    if video.audio is None:
        return video
    fade_duration = min(DECLICK_FADE_SECONDS, video.duration / 2)
    video.audio = video.audio.with_effects(
        [AudioFadeIn(fade_duration), AudioFadeOut(fade_duration)]
    )
    return video


def build_trimmed_subclips(clip_paths: list):
    from moviepy import VideoFileClip

    subclips = []
    for path in clip_paths:
        video = VideoFileClip(str(path))
        span = _speaking_span(path)
        if span is None:
            print(
                f"  {path.name}: no speech detected, using full clip ({video.duration:.1f}s)"
            )
            subclips.append(_declicked(video))
            continue

        start = max(0.0, span[0] - LEAD_PADDING_SECONDS)
        end = min(video.duration, span[1] + TAIL_PADDING_SECONDS)
        print(
            f"  {path.name}: trimmed {video.duration:.1f}s -> [{start:.1f}s, {end:.1f}s] ({end - start:.1f}s)"
        )
        subclips.append(_declicked(video.subclipped(start, end)))

    return subclips


def stitch(clips_dir: Path, output_path: Path):
    from moviepy import concatenate_videoclips

    clip_paths = sorted(Path(clips_dir).glob("*.mp4"))
    if not clip_paths:
        raise FileNotFoundError(f"No .mp4 files found in {clips_dir}")

    print(f"Stitching {len(clip_paths)} clips in filename order:")
    subclips = build_trimmed_subclips(clip_paths)

    final = concatenate_videoclips(subclips, method="compose")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-movflags", "+faststart"],
    )

    for sc in subclips:
        sc.close()
    final.close()

    print(f"\nDone: {output_path} ({final.duration:.1f}s)")
    return output_path
