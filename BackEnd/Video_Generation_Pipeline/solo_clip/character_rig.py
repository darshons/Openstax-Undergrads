# Derives a fixed, reusable pose + camera + backdrop assignment per
# character in a scenario, used identically across every solo clip of that
# character throughout the lesson (see solo_clip/pipeline.py).
#
# This generalizes what would otherwise be hand-authored per lesson into one
# LLM call that reads the scenario's characters, room setting, and any
# position hints, and produces the same kind of assignment automatically for
# an arbitrary scenario.
#
# The LLM only supplies the content-specific parts (what position, what's
# behind them) - the wording for "this never changes" / "nothing else is
# visible" stays fixed in code, since that phrasing is what's been validated
# to work across many real generations. Only the facts about this
# particular room and cast are left to the model.
import json
from pathlib import Path

RIG_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """
You are staging a training-simulation video that will be filmed as a series
of isolated single-character shots - every clip shows exactly one character
speaking, alone, and clips of different characters are cut together in
editing afterward. For this to look like a coherent scene, each character
needs ONE fixed body position and ONE fixed, distinct backdrop that stays
completely identical across every clip of that character in this scenario -
like a locked camera setup you would light and shoot once, then reuse.

For each character, decide:
1. pose_core: a single fixed, static body position for this character -
   standing or sitting, consistent with their role (e.g. a bedridden
   patient sits in bed, staff typically stand). One or two sentences,
   physical position only (posture, hands, weight) - not an action or
   gesture, since this position never changes across the character's shots.
2. backdrop_core: what specific furniture, equipment, or room features are
   visible directly behind this character. Use ONLY items actually
   mentioned in the setting/furniture/equipment description provided - do
   not invent props. Each character's backdrop must be visibly DISTINCT
   from every other character's backdrop - assign different, non-overlapping
   room features to each person so that cutting between characters reads as
   two different camera setups in the same room, not the same shot reused
   with a different person swapped in.
3. gaze_direction: either "screen_left" or "screen_right" - which way this
   character's head and eyes should be turned, off-camera, as if looking
   toward whoever they are conversing with in the room. Base this on the
   character's position relative to the others (someone positioned on the
   left side of the room typically turns toward screen_right to face
   whoever is to their right, and vice versa). This character is never
   looking directly into the camera lens.

If the input includes explicit initial character positions, treat that as
the strongest signal for pose and gaze_direction. If the room does not have
enough distinct furniture/equipment for every character to get a fully
unique backdrop, do your best to differentiate by describing a different
direction/angle within the room instead (e.g. "the wall behind them,
without the window" vs "the corner near the door").

Respond with ONLY a JSON object, no other text, in this exact shape:
{
  "<character_id>": {
    "pose_core": "...",
    "backdrop_core": "...",
    "gaze_direction": "screen_left" | "screen_right"
  },
  ...
}
Include every character_id given in the input, no more, no fewer.
"""


def setting_summary(scenario: dict) -> str:
    """Handles both scenario schemas seen so far: a top-level 'setting'
    object with structured furniture/equipment lists, or per-scene 'setting'
    prose plus 'character_actions' (older format, room described in text)."""
    setting = scenario.get("setting")
    if isinstance(setting, dict):
        parts = [
            f"Location: {setting.get('location', '')}",
            f"Description: {setting.get('scene_description', '')}",
        ]
        furniture = setting.get("background_furniture") or []
        equipment = setting.get("background_equipment") or []
        if furniture:
            parts.append(
                "Furniture: "
                + "; ".join(f"{f.get('name')} ({f.get('description', '')})" for f in furniture)
            )
        if equipment:
            parts.append(
                "Equipment: "
                + "; ".join(f"{e.get('name')} ({e.get('description', '')})" for e in equipment)
            )
        return "\n".join(parts)

    scenes = scenario.get("scenes", [])
    if scenes:
        first = scenes[0]
        return (
            f"Setting: {first.get('setting', '')}\n"
            f"Character actions (for room layout context): {first.get('character_actions', '')}"
        )
    return ""


def _initial_positions_summary(scenario: dict) -> str:
    scenes = scenario.get("scenes", [])
    if not scenes:
        return ""
    positions = scenes[0].get("initial_character_positions")
    if not positions:
        return ""
    return "\n".join(f"{p.get('character_id')}: {p.get('position', '')}" for p in positions)


def _character_summary(characters: list) -> str:
    lines = []
    for c in characters:
        a = c.get("appearance", {})
        lines.append(f"{c['character_id']} ({c.get('name')}, {c.get('role')}): {a.get('build', '')}")
    return "\n".join(lines)


def generate_character_rig(client, scenario: dict) -> dict:
    """Returns {character_id: {"pose": str, "backdrop": str, "camera": {...}}}
    with a fixed pose/camera/backdrop for every character in the scenario,
    derived once and reused across every scene and clip. One cheap text
    generation call - not a video generation call."""
    from google.genai import types

    characters = scenario["characters"]
    character_ids = [c["character_id"] for c in characters]

    user_prompt = (
        f"Characters:\n{_character_summary(characters)}\n\n"
        f"Room setting:\n{setting_summary(scenario)}\n\n"
        f"Initial character positions (if given):\n{_initial_positions_summary(scenario)}\n"
    )

    response = client.models.generate_content(
        model=RIG_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )
    raw = json.loads(response.text)

    missing = set(character_ids) - set(raw.keys())
    if missing:
        raise ValueError(f"character_rig: LLM response missing characters {missing}")

    lookup = {c["character_id"]: c for c in characters}
    rig = {}
    for cid in character_ids:
        name = lookup[cid]["name"]
        pose_core = raw[cid]["pose_core"]
        backdrop_core = raw[cid]["backdrop_core"]
        gaze_direction = raw[cid].get("gaze_direction", "screen_left")
        gaze_side = "screen left" if gaze_direction == "screen_left" else "screen right"

        pose = (
            f"{pose_core} This exact position is identical in every shot of "
            f"{name} in this scene - they do not move, walk, or change position."
        )
        camera_angle = (
            f"Static medium shot on {name} only, framed from the waist up, "
            f"camera at their eye level, {name} centered in frame. This exact "
            f"camera distance, height, and angle is identical in every shot of "
            f"{name} in this scene. Directly behind {name}: {backdrop_core}. "
            f"Nothing associated with other characters is visible in {name}'s "
            f"shots - it is out of frame behind the camera. "
            f"{name}'s head and eyes are turned away from the camera at roughly "
            f"a 45-degree angle toward {gaze_side}, as though looking at someone "
            f"they are talking to just out of frame - {name} does not make direct "
            f"eye contact with the camera lens and never faces the camera "
            f"head-on. This exact head angle and gaze direction is identical in "
            f"every shot of {name} in this scene."
        )
        rig[cid] = {
            "pose": pose,
            "backdrop": backdrop_core,
            "camera": {
                "angle": camera_angle,
                "movement": "Static.",
                "lens_effect": "Shallow depth of field, neutral warm tone, identical lighting in every shot.",
            },
        }
    return rig


def rig_cache_path(output_dir: Path) -> Path:
    return output_dir / "character_rig.json"


def load_cached_rig(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rig_cache(path: Path, rig: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rig, f, indent=2)
