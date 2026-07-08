import json

FRAMES_PER_SEGMENT = 4

# Gemini 2.5 Flash pricing (input tokens only — judge calls are input-heavy).
# An image ~= 258 tokens at this resolution tier. Source: https://ai.google.dev/pricing
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_INPUT_COST_PER_1M_TOKENS = 0.30
TOKENS_PER_IMAGE = 258
TEXT_PROMPT_TOKENS_ESTIMATE = 200


def estimate_judge_cost(num_calls: int) -> float:
    tokens_per_call = TEXT_PROMPT_TOKENS_ESTIMATE + FRAMES_PER_SEGMENT * TOKENS_PER_IMAGE
    total_tokens = num_calls * tokens_per_call
    return round(total_tokens / 1_000_000 * GEMINI_INPUT_COST_PER_1M_TOKENS, 4)


def sample_frames(video_path: str, start: float, end: float, count: int = FRAMES_PER_SEGMENT) -> list:
    """Return `count` evenly-spaced frames (as raw bytes) from [start, end]."""
    import io
    from moviepy import VideoFileClip
    from PIL import Image

    video = VideoFileClip(video_path)
    frames = []
    span = max(end - start, 0.01)
    for i in range(count):
        t = start + span * (i + 0.5) / count
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
        "the frames, which character is speaking?\n\n"
        f"Characters in this scene:\n{char_lines}\n\n"
        "Respond with strict JSON: "
        '{"character_id": "<id or null if unclear>", "rationale": "<one sentence>"}'
    )


def judge_segment_speaker(client, video_path: str, start: float, end: float, characters: list) -> dict:
    """Ask a vision LLM who is speaking across one Whisper segment's time span."""
    from google.genai import types

    frames = sample_frames(video_path, start, end)
    parts = [types.Part.from_bytes(data=f, mime_type="image/jpeg") for f in frames]
    parts.append(types.Part.from_text(text=_build_prompt(characters)))

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Content(role="user", parts=parts)],
    )

    try:
        parsed = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        parsed = {"character_id": None, "rationale": "unparseable model response"}

    return {
        "start": start,
        "end": end,
        "judged_speaker": parsed.get("character_id"),
        "rationale": parsed.get("rationale"),
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


def judge_speakers(client, video_path: str, segments: list, dialogue: list, characters: list) -> dict:
    """Judge speaker identity for every Whisper segment in a clip, and compare
    the resulting speaker sequence to the expected order from scenario.json.

    Sequence comparison (not 1:1 index matching) since segment count and line
    count don't need to align — Veo may split or merge lines mid-clip.
    """
    judged = [
        judge_segment_speaker(client, video_path, seg["start"], seg["end"], characters)
        for seg in segments
    ]

    judged_order = _collapse_consecutive([j["judged_speaker"] for j in judged if j["judged_speaker"]])
    expected_order = _collapse_consecutive([d["character_id"] for d in dialogue])

    return {
        "segments": judged,
        "expected_speaker_order": expected_order,
        "attribution_passed": judged_order == expected_order,
        "estimated_cost_usd": estimate_judge_cost(len(segments)),
    }
