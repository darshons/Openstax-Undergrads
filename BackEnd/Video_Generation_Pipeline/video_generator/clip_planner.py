import json

from google.genai import types

from Script_Generation_Pipeline import setup_gemini_client

MODEL = "gemini-3.1-pro-preview"

# Reference images are always supplied per scene (background + all characters),
# which forces every scene's first clip to this duration regardless of
# duration_seconds — see generate_first_clip's reference-image branch in
# veo_api.py. Every clip after the first is a fixed-length extension.
FIRST_CLIP_SECONDS = 8
EXTENSION_SECONDS = 7
MIN_CLIPS = 1
# Generous ceiling for realistic 15-40s scenes, well under Veo's ~21-clip cap.
MAX_CLIPS_PER_SCENE = 6
MAX_PLANNING_ATTEMPTS = 3


class ClipPlanningError(RuntimeError):
    """Raised when the model's clip breakdown fails validation against the source scene."""


def suggested_clip_count(duration_seconds: int) -> int:
    """Estimate how many Veo clips it takes to approximate a scene's target
    duration: one FIRST_CLIP_SECONDS clip plus N EXTENSION_SECONDS extensions."""
    if duration_seconds <= FIRST_CLIP_SECONDS:
        return MIN_CLIPS
    extra = max(1, round((duration_seconds - FIRST_CLIP_SECONDS) / EXTENSION_SECONDS))
    return min(MAX_CLIPS_PER_SCENE, 1 + extra)


def _dialogue_key(line: dict) -> tuple:
    return (line.get("character_id"), line.get("line"))


def _validate_clips(clips: list, original_dialogue: list, num_clips: int) -> None:
    if len(clips) != num_clips:
        raise ClipPlanningError(
            f"expected {num_clips} clips, model returned {len(clips)}"
        )

    collected_dialogue = []
    for i, clip in enumerate(clips, start=1):
        if not clip.get("character_actions"):
            raise ClipPlanningError(f"clip {i} is missing character_actions")
        if not clip.get("camera"):
            raise ClipPlanningError(f"clip {i} is missing camera")
        collected_dialogue.extend(clip.get("dialogue", []))

    expected = [_dialogue_key(line) for line in original_dialogue]
    actual = [_dialogue_key(line) for line in collected_dialogue]
    if actual != expected:
        raise ClipPlanningError(
            "clip dialogue must reuse every original line verbatim and in order "
            f"(expected {expected!r}, got {actual!r})"
        )


def plan_scene_clips(
    scene: dict, characters: list, visual_style: str, client=None
) -> dict:
    """Break one authored scene (flat audio/camera/duration) into the `clips`
    breakdown Veo's extension pipeline needs — a per-beat list of dialogue
    chunk + camera + actions, one entry per Veo clip. Returns a new scene dict
    with `clips` populated; every other scene field is passed through unchanged.

    Raises ClipPlanningError if the model doesn't preserve every original
    dialogue line verbatim and in order — clips may only group existing
    lines, never invent, drop, reorder, or paraphrase them.
    """
    client = client or setup_gemini_client()

    dialogue = scene.get("audio", {}).get("dialogue", [])
    num_clips = suggested_clip_count(scene.get("duration_seconds", FIRST_CLIP_SECONDS))

    scene_context = {
        "visual_style": visual_style,
        "characters": characters,
        "scene": {
            "scene_id": scene.get("scene_id"),
            "scene_summary": scene.get("scene_summary", ""),
            "character_actions": scene.get("character_actions", ""),
            "initial_character_positions": scene.get("initial_character_positions", []),
            "dialogue": dialogue,
            "on_screen_text": scene.get("on_screen_text"),
        },
        "num_clips": num_clips,
    }

    system_prompt = f"""
    You are breaking one scene of an interactive training-simulation script into a shot list for an AI video generator that renders clips in sequence, each one continuing directly from the last.

    You will be given the scene's full description, its dialogue (in order), the characters present, and the visual style. Break it into exactly {num_clips} clips, each covering one continuous beat of action (roughly 5-10 seconds of screen time).

    Rules for the dialogue:
    - Every dialogue line in the input must appear in your output exactly once, verbatim, in the same order.
    - Do not paraphrase, merge, split, reorder, or invent dialogue lines.
    - A clip may have zero dialogue lines if it is a pure action/reaction beat.

    Rules for character_actions:
    - Write a concise, present-tense description of physical action/blocking for just that clip's beat.
    - Each clip should continue naturally from the physical state the previous clip ended in (position, posture, ongoing gesture) — do not reset or restate earlier action.

    Rules for camera:
    - Provide "angle", "movement", and "lens_effect" for each clip.
    - Camera can change between clips (new angle, push in, cut to reaction), but stay consistent with the visual style and scene's established setting.

    The scene's on_screen_text (if any) belongs only on the final clip.

    Output strictly as a JSON object of the form {{"clips": [{{"clip_id": 1, "character_actions": "...", "camera": {{"angle": "...", "movement": "...", "lens_effect": "..."}}, "dialogue": [{{"character_id": "...", "line": "..."}}], "on_screen_text": "..."}}]}} with no additional text before or after. Omit "on_screen_text" on every clip except the last, and only if the scene has one.
    """

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
    )

    # response_mime_type="application/json" makes malformed JSON rare, but not
    # impossible — observed in practice even on a well-formed prompt. A
    # transient bad completion is worth one retry before treating it as a
    # real planning failure, mirroring the retry-on-transient-failure pattern
    # already used elsewhere in this pipeline (veo_api.py, clip_verification.py).
    last_error: Exception | None = None
    for attempt in range(MAX_PLANNING_ATTEMPTS):
        response = client.models.generate_content(
            model=MODEL,
            contents=[json.dumps(scene_context, indent=2)],
            config=config,
        )

        try:
            if not response or not response.text:
                raise ClipPlanningError(
                    f"scene {scene.get('scene_id')}: no response from model"
                )

            parsed = json.loads(response.text)
            clips = parsed.get("clips")
            if clips is None:
                raise ClipPlanningError(
                    f"scene {scene.get('scene_id')}: response missing 'clips'"
                )

            _validate_clips(clips, dialogue, num_clips)

            for i, clip in enumerate(clips, start=1):
                clip.setdefault("clip_id", i)

            return {**scene, "clips": clips}

        except (json.JSONDecodeError, ClipPlanningError) as e:
            last_error = e
            print(
                f"  [clip_planner] scene {scene.get('scene_id')} attempt "
                f"{attempt + 1}/{MAX_PLANNING_ATTEMPTS} failed: {e}"
            )

    raise ClipPlanningError(
        f"scene {scene.get('scene_id')}: still failing after "
        f"{MAX_PLANNING_ATTEMPTS} attempts: {last_error}"
    )


def plan_scenario_clips(scenario: dict, client=None) -> dict:
    """Run plan_scene_clips over every scene in a scenario, returning a new
    scenario dict with `clips` populated on each scene."""
    client = client or setup_gemini_client()
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]

    planned_scenes = [
        plan_scene_clips(scene, characters, visual_style, client=client)
        for scene in scenario["scenes"]
    ]
    return {**scenario, "scenes": planned_scenes}
