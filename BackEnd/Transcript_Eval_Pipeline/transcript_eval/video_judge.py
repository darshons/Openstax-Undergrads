import json
import time
from datetime import datetime

from pydantic import BaseModel

from .report_utils import save_eval_report

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_INPUT_COST_PER_1M_TOKENS = 1.5
# Gemini samples video at ~1fps and ingests audio in the same pass; ~263
# tokens/sec is the documented combined rate at default media resolution.
# Source: https://ai.google.dev/gemini-api/docs/vision#technical-details-video
VIDEO_TOKENS_PER_SECOND = 263
TEXT_PROMPT_TOKENS_ESTIMATE = 300

FILE_UPLOAD_POLL_SECONDS = 2
FILE_UPLOAD_TIMEOUT_SECONDS = 60


def estimate_video_judge_cost(duration_seconds: float) -> float:
    tokens = TEXT_PROMPT_TOKENS_ESTIMATE + duration_seconds * VIDEO_TOKENS_PER_SECOND
    return round(tokens / 1_000_000 * GEMINI_INPUT_COST_PER_1M_TOKENS, 4)


def _build_prompt(
    dialogue: list, characters: list, setting: str, character_actions: str
) -> str:
    char_lines = "\n".join(
        f"- {c['character_id']} ({c['name']}): {c.get('appearance', {})}"
        for c in characters
    )
    dialogue_lines = "\n".join(
        f'{i + 1}. {d["character_id"]}: "{d["line"]}"' for i, d in enumerate(dialogue)
    )
    return (
        "You are watching one continuous video clip with audio, generated for a "
        "training scenario. Judge it against the script below using both the audio "
        "and the visuals.\n\n"
        f"Characters:\n{char_lines}\n\n"
        f"Expected setting: {setting}\n"
        f"Expected actions in this clip: {character_actions}\n"
        f"Expected dialogue (in order):\n{dialogue_lines}\n\n"
        "Check three things, most important first:\n"
        "1. VISUAL CONSISTENCY: the bar here is physical plausibility, not a literal "
        "match to the expected setting/actions below — those are background context, "
        "not a checklist. Only flag something if it is physically impossible or "
        "logically incoherent: a person or object appearing/disappearing without "
        "explanation, a body bending or moving in an anatomically impossible way, "
        "objects clipping through each other or floating unsupported, or a character's "
        "position jumping between frames with no continuous motion. Do NOT flag a scene "
        "just because it differs from the expected setting/actions, includes an object "
        "or person not explicitly mentioned, or has minor stylistic/lighting variation — "
        "as long as what's shown is physically coherent, it's fine.\n"
        "2. DIALOGUE CONSISTENCY: this is about correct speaker attribution, not "
        "frame-perfect lip-sync timing. For each expected line, the character_id who "
        "says it in the script above should be the one whose mouth is moving while that "
        "line plays, and no other character's mouth should be visibly moving at the same "
        "time. Minor timing drift between audio and mouth movement (not perfectly "
        "synced word-for-word) is fine and should not be flagged. Only flag it if the "
        "wrong character's mouth is moving for a line, more than one character appears "
        "to be talking at once, or the speaking character's mouth never moves while "
        "their line plays.\n"
        "3. SCRIPT ALIGNMENT (less important than the above — only flag a clear "
        "mismatch): does the spoken dialogue achieve what the script specifies, "
        "allowing for paraphrasing?\n\n"
        "Respond with strict JSON: "
        '{"visual_issues_found": bool, "visual_notes": "<one sentence>", '
        '"dialogue_issues_found": bool, "dialogue_notes": "<one sentence>", '
        '"script_alignment_issues_found": bool, "script_alignment_notes": "<one sentence>", '
        '"confidence": "high"|"low"}'
    )


class _VideoJudgment(BaseModel):
    visual_issues_found: bool
    visual_notes: str
    dialogue_issues_found: bool
    dialogue_notes: str
    script_alignment_issues_found: bool
    script_alignment_notes: str
    confidence: str


def _upload_and_wait(client, video_path: str):
    """Gemini processes an uploaded video asynchronously — poll until it leaves
    PROCESSING before referencing it in generate_content."""
    video_file = client.files.upload(file=video_path)
    elapsed = 0
    while (
        video_file.state.name == "PROCESSING" and elapsed < FILE_UPLOAD_TIMEOUT_SECONDS
    ):
        time.sleep(FILE_UPLOAD_POLL_SECONDS)
        elapsed += FILE_UPLOAD_POLL_SECONDS
        video_file = client.files.get(name=video_file.name)
    return video_file


def judge_video(
    client,
    video_path: str,
    dialogue: list,
    characters: list,
    setting: str,
    character_actions: str,
) -> dict:
    """Whole-clip Gemini judge over native video+audio (not sampled frames), covering
    visual consistency, dialogue/lip-sync attribution, and script alignment in one call.

    Standalone: not wired into evaluate_clip()'s overall pass/fail — it's meant to be
    compared against the existing per-check pipeline before deciding whether to adopt,
    replace, or gate on it. A script-alignment mismatch alone never fails this judge;
    only a high-confidence visual or dialogue issue does.
    """
    from moviepy import VideoFileClip
    from google.genai import types

    duration = VideoFileClip(video_path).duration

    video_file = _upload_and_wait(client, video_path)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=video_file.uri, mime_type=video_file.mime_type
                    ),
                    types.Part.from_text(
                        text=_build_prompt(
                            dialogue, characters, setting, character_actions
                        )
                    ),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_VideoJudgment,
        ),
    )

    judgment = response.parsed
    if judgment is None:
        try:
            judgment = _VideoJudgment.model_validate_json(response.text)
        except (json.JSONDecodeError, ValueError, AttributeError):
            judgment = None

    if judgment is None:
        return {
            "visual_issues_found": False,
            "visual_notes": "unparseable model response",
            "dialogue_issues_found": False,
            "dialogue_notes": "unparseable model response",
            "script_alignment_issues_found": False,
            "script_alignment_notes": "unparseable model response",
            "confidence": "low",
            "status": "pass",
            "estimated_cost_usd": estimate_video_judge_cost(duration),
        }

    status = (
        "fail"
        if (
            judgment.confidence == "high"
            and (judgment.visual_issues_found or judgment.dialogue_issues_found)
        )
        else "pass"
    )

    return {
        "visual_issues_found": judgment.visual_issues_found,
        "visual_notes": judgment.visual_notes,
        "dialogue_issues_found": judgment.dialogue_issues_found,
        "dialogue_notes": judgment.dialogue_notes,
        "script_alignment_issues_found": judgment.script_alignment_issues_found,
        "script_alignment_notes": judgment.script_alignment_notes,
        "confidence": judgment.confidence,
        "status": status,
        "estimated_cost_usd": estimate_video_judge_cost(duration),
    }


def evaluate_clip(
    client,
    video_path: str,
    scene_id: int,
    clip_id: int,
    dialogue: list,
    characters: list,
    setting: str = "",
    character_actions: str = "",
) -> dict:
    """Drop-in replacement for eval.evaluate_clip(): gates pass/fail on this
    module's whole-clip video judge instead of the legacy transcribe +
    match_dialogue + judge_speaker + consistency_check pipeline. Same report
    contract (timestamp/scene_id/clip_id/video_path/estimated_cost_usd/passed)
    the legacy evaluator used, so callers built against it (clip_verification.py,
    pipeline.py) only need to swap which evaluate_clip they import.
    """
    video_judgment = judge_video(
        client, video_path, dialogue, characters, setting, character_actions
    )

    report = {
        "timestamp": datetime.now().isoformat(),
        "scene_id": scene_id,
        "clip_id": clip_id,
        "video_path": video_path,
        "video_judge": video_judgment,
        "estimated_cost_usd": video_judgment.get("estimated_cost_usd", 0.0),
        "passed": video_judgment["status"] == "pass",
    }

    save_eval_report(video_path, report)
    return report
