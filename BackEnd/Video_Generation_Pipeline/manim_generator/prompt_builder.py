"""Fill the manim_generator prompt templates from a ScenarioSpec.

Block-formatting conventions (character block, numbered do-not-swap dialogue)
mirror video_generator/prompt_builder.py so the script-gen pipeline's promise
that character appearance strings "may be reused verbatim in future
video-generation prompts" holds for the Manim path too.
"""

from .code_generator import fill_prompt, load_prompt
from .kokoro_voiceover import KNOWN_VOICES
from .script_adapter import Scene, ScenarioSpec

# Average conversational TTS rate; Kokoro at speed 1.0 lands near this.
TTS_WORDS_PER_SECOND = 2.7


def estimate_tts_seconds(text: str) -> float:
    return round(max(1.0, len(text.split()) / TTS_WORDS_PER_SECOND), 1)


def build_character_block(spec: ScenarioSpec) -> str:
    lines = []
    for c in spec.characters:
        a = c.appearance
        details = [
            f"{a.get('skin_tone', '')} skin",
            a.get("hair", ""),
            a.get("build", ""),
            a.get("uniform", ""),
        ]
        if a.get("distinguishing_features"):
            details.append(f"distinguishing features: {a['distinguishing_features']}")
        lines.append(
            f"- {c.name} ({c.role}) [character_id: {c.character_id}]: "
            + ", ".join(d for d in details if d)
            + f". Emotional tone: {c.emotional_baseline}."
        )
    return "\n".join(lines)


def build_setting_block(spec: ScenarioSpec, scene: Scene | None = None) -> str:
    if scene is not None and scene.setting_override:
        return scene.setting_override
    if not spec.setting:
        return "(no setting specified — use a neutral interior backdrop)"
    parts = []
    for key, value in spec.setting.items():
        if key in ("background_furniture", "background_equipment") and isinstance(value, list):
            items = ", ".join(
                f"{item.get('count', 1)}x {item.get('name', '')} ({item.get('description', '')})"
                for item in value
            )
            parts.append(f"{key.replace('_', ' ')}: {items}")
        elif isinstance(value, dict):
            parts.append(f"{key}: " + ", ".join(f"{k}={v}" for k, v in value.items()))
        else:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def build_dialogue_block(spec: ScenarioSpec, scene: Scene, with_estimates: bool = False) -> str:
    chars = spec.characters_by_id
    lines = []
    for idx, d in enumerate(scene.dialogue, start=1):
        char = chars.get(d.character_id)
        name = char.name if char else d.character_id
        est = f" (~{estimate_tts_seconds(d.line)}s)" if with_estimates else ""
        lines.append(f'{idx}. {name} [character_id: {d.character_id}]: "{d.line}"{est}')
    if lines:
        return (
            "Spoken in this exact order — each character delivers only their own numbered line:\n"
            + "\n".join(lines)
            + "\nDo not swap, merge, or reorder lines between characters."
        )
    return "None — no spoken words in this scene. Characters act silently; do not invent dialogue."


TYPE_GUIDANCE = {
    "narrative": (
        "**Scene-type guidance (narrative):** This scene sets up a situation that leads into a "
        "decision. Establish the setting and characters, build the tension described in the "
        "summary, and end on the unresolved moment — do NOT resolve it or hint at the right answer."
    ),
    "consequence": (
        "**Scene-type guidance (consequence):** The learner chose a WRONG option. Show the "
        "misconception playing out naturally through the characters — the negative or unhelpful "
        "outcome should be visible in the scene, without any 'you were wrong' messaging. End on a "
        "reflective beat that visually returns to the open question (the learner will retry the "
        "decision after this clip)."
    ),
    "resolution": (
        "**Scene-type guidance (resolution):** The learner chose the CORRECT option. Show the "
        "positive outcome and make the underlying reasoning visible — reinforce WHY this works, "
        "grounded in the learning goal. End settled and forward-looking (the story continues)."
    ),
}


def build_asset_kit_prompt(spec: ScenarioSpec) -> str:
    suggested = ", ".join(f"{c.character_id} -> {c.voice}" for c in spec.characters)
    return fill_prompt(
        load_prompt("prompt_asset_kit"),
        visual_style=spec.visual_style or "clean 2D semi-flat educational motion graphics",
        character_block=build_character_block(spec),
        setting_block=build_setting_block(spec),
        known_voices=", ".join(KNOWN_VOICES),
        suggested_voices=suggested,
    )


def build_scene_plan_prompt(spec: ScenarioSpec, scene: Scene, asset_api: str) -> str:
    positions = "; ".join(
        f"{p.get('character_id', '?')}: {p.get('position', '')}" for p in scene.initial_positions
    ) or "(not specified)"
    sound_notes = "; ".join(x for x in (scene.sound_effects, scene.ambience) if x) or "(none)"
    return fill_prompt(
        load_prompt("prompt_scene_plan"),
        title=spec.title,
        learning_goal=spec.learning_goal,
        target_audience=spec.target_audience,
        visual_style=spec.visual_style,
        scene_id=scene.scene_id,
        scene_type=scene.scene_type,
        scene_summary=scene.summary,
        duration_seconds=scene.duration_seconds or 20,
        character_actions=scene.character_actions,
        initial_positions=positions,
        sound_notes=sound_notes,
        dialogue_block=build_dialogue_block(spec, scene, with_estimates=True),
        type_guidance=TYPE_GUIDANCE.get(scene.scene_type, TYPE_GUIDANCE["narrative"]),
        asset_api=asset_api,
    )


def build_code_prompt(spec: ScenarioSpec, scene: Scene, scene_plan: str, asset_api: str) -> str:
    return fill_prompt(
        load_prompt("prompt_code_generation"),
        title=spec.title,
        visual_style=spec.visual_style,
        scene_plan=scene_plan,
        scene_id=scene.scene_id,
        dialogue_block=build_dialogue_block(spec, scene),
        asset_api=asset_api,
    )
