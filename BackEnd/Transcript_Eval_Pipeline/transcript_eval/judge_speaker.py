import json

from pydantic import BaseModel

FRAMES_PER_SEGMENT = 4

# Gemini 2.5 Flash pricing (input tokens only — judge calls are input-heavy).
# An image ~= 258 tokens at this resolution tier. Source: https://ai.google.dev/pricing
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_INPUT_COST_PER_1M_TOKENS = 0.30
TOKENS_PER_IMAGE = 258
TEXT_PROMPT_TOKENS_ESTIMATE = 200


def estimate_judge_cost(num_calls: int) -> float:
    tokens_per_call = (
        TEXT_PROMPT_TOKENS_ESTIMATE + FRAMES_PER_SEGMENT * TOKENS_PER_IMAGE
    )
    total_tokens = num_calls * tokens_per_call
    return round(total_tokens / 1_000_000 * GEMINI_INPUT_COST_PER_1M_TOKENS, 4)


def sample_frames(video_path: str, start: float, end: float, count: int = FRAMES_PER_SEGMENT) -> list:
    """Return `count` evenly-spaced frames (as raw bytes) from [start, end].

    Sampled at (i+1)/(count+1) rather than the segment's true edges — frames
    right at a segment boundary tend to catch a speaker mid-transition
    (e.g. still opening their mouth from the prior line), which confuses the
    judge on intense multi-speaker dialogue.
    """
    import io
    from moviepy import VideoFileClip
    from PIL import Image

    video = VideoFileClip(video_path)
    frames = []
    span = max(end - start, 0.01)
    for i in range(count):
        t = start + span * (i + 1) / (count + 1)
        t = min(t, video.duration - 0.01)
        frame = video.get_frame(t)
        buf = io.BytesIO()
        Image.fromarray(frame).save(buf, format="JPEG")
        frames.append(buf.getvalue())
    video.close()
    return frames


def _build_prompt(characters: list) -> str:
    char_lines = "\n".join(
        f"- {c['character_id']} ({c['name']}): {c.get('appearance', {})}"
        for c in characters
    )
    return (
        "These frames are sampled in order across one continuous line of dialogue "
        "in a video. Based on lip movement, gesture, and body orientation across "
        "the frames, which character(s) appear to be actively speaking?\n\n"
        f"Characters in this scene:\n{char_lines}\n\n"
        "List every character who appears to be speaking — usually this is exactly "
        "one, but list more than one if several characters' mouths are moving "
        "in a way that suggests speech, and list none if it's unclear or no one "
        "appears to be speaking.\n\n"
        "Respond with strict JSON: "
        '{"speaking_characters": ["<id>", ...], "rationale": "<one sentence>"}'
    )


class _SpeakerJudgment(BaseModel):
    speaking_characters: list[str]
    rationale: str


def judge_segment_speaker(client, video_path: str, start: float, end: float, characters: list) -> dict:
    """Ask a vision LLM who is speaking across one Whisper segment's time span.

    A segment is only counted as a clean, single-speaker judgment when exactly
    one character is reported speaking. Zero (unclear) or multiple (ambiguous —
    e.g. a reaction shot where both characters' mouths are moving) are both
    surfaced explicitly rather than forcing a guess, since a forced single
    answer here would silently corrupt the speaker-sequence comparison.
    """
    from google.genai import types

    frames = sample_frames(video_path, start, end)
    parts = [types.Part.from_bytes(data=f, mime_type="image/jpeg") for f in frames]
    parts.append(types.Part.from_text(text=_build_prompt(characters)))

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_SpeakerJudgment,
        ),
    )

    # response_schema makes Gemini emit schema-conformant JSON directly, so
    # response.parsed is populated in the normal case; json.loads(response.text)
    # is only a fallback for the rare case the SDK couldn't coerce it.
    judgment = response.parsed
    if judgment is None:
        try:
            judgment = _SpeakerJudgment.model_validate_json(response.text)
        except (json.JSONDecodeError, ValueError, AttributeError):
            judgment = None

    candidates = judgment.speaking_characters if judgment else []
    rationale = judgment.rationale if judgment else "unparseable model response"

    return {
        "start": start,
        "end": end,
        "candidates": candidates,
        "judged_speaker": candidates[0] if len(candidates) == 1 else None,
        "ambiguous": len(candidates) > 1,
        "rationale": rationale,
    }


def _collapse_consecutive(speakers: list) -> list:
    """Collapse runs of the same speaker into one entry, so a line that gets
    split across multiple segments (or a segment spanning multiple lines from
    the same speaker) doesn't break the sequence comparison."""
    collapsed = []
    for speaker in speakers:
        if not collapsed or collapsed[-1] != speaker:
            collapsed.append(speaker)
    return collapsed


def judge_speakers(
    client, video_path: str, segments: list, dialogue: list, characters: list
) -> dict:
    """Judge speaker identity for every Whisper segment in a clip, and compare
    the resulting speaker sequence to the expected order from scenario.json.

    Sequence comparison (not 1:1 index matching) since segment count and line
    count don't need to align — Veo may split or merge lines mid-clip.

    Only segments with exactly one detected speaker feed the sequence — segments
    where nobody or multiple characters appear to be speaking are excluded (a
    forced single answer there would be a guess, not a judgment) and are instead
    counted separately so a clip with too many ambiguous segments to draw a
    reliable conclusion from is visible in the report rather than silently
    passing or failing on noise.
    """
    judged = [
        judge_segment_speaker(client, video_path, seg["start"], seg["end"], characters)
        for seg in segments
    ]

    judged_order = _collapse_consecutive(
        [j["judged_speaker"] for j in judged if j["judged_speaker"]]
    )
    expected_order = _collapse_consecutive([d["character_id"] for d in dialogue])
    ambiguous_count = sum(1 for j in judged if j["ambiguous"])
    inconclusive_count = sum(
        1 for j in judged if j["judged_speaker"] is None and not j["ambiguous"]
    )

    return {
        "segments": judged,
        "expected_speaker_order": expected_order,
        "ambiguous_segments": ambiguous_count,
        "inconclusive_segments": inconclusive_count,
        "attribution_passed": judged_order == expected_order,
        "estimated_cost_usd": estimate_judge_cost(len(segments)),
    }
