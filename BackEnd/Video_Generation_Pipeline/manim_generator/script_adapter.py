"""Adapt a Scenario Studio script JSON into a normalized ScenarioSpec.

The script shape is produced by Script_Generation_Pipeline (see
_JSON_Templates/script_gen_with_dpoints.json) and edited in the frontend
(frontend/src/types/script.ts). Two dialects exist in the wild; this module
normalizes both:

- scene "type" vs "scene_type"
- audio.dialogue[{character_id, line, character_position}] vs
  audio.clips[{character_id, dialogue}]
- root-level setting object (keys vary: "light_source" vs "lighting") vs
  per-scene setting strings

Branch topology (validated here): each decision point has exactly one correct
choice; incorrect choices route to consequence scenes that loop back to the
same decision point; the correct choice routes to a resolution scene that
continues the trunk.
"""

import json
from dataclasses import dataclass, field

# Fallback Kokoro voice rotation, deterministic by character order of
# appearance. The asset-kit generation step may override this with a
# VOICE_MAP inferred from the character descriptions.
FALLBACK_VOICES = [
    "af_sarah",
    "am_michael",
    "bf_emma",
    "bm_george",
    "af_nicole",
    "am_adam",
]
DEFAULT_VOICE = "af_sarah"


class ScriptValidationError(ValueError):
    """Raised when the script's branch graph is inconsistent."""


@dataclass
class DialogueLine:
    character_id: str
    line: str
    position: str = ""


@dataclass
class Character:
    character_id: str
    name: str
    role: str
    appearance: dict
    emotional_baseline: str
    voice: str = DEFAULT_VOICE


@dataclass
class Choice:
    choice_id: str
    text: str
    is_correct: bool
    misconception: str | None
    routes_to_scene: int | None


@dataclass
class DecisionPoint:
    decision_point_id: int
    question_text: str
    intro_scene_id: int | None
    choices: list[Choice]

    @property
    def correct_choice(self) -> Choice:
        return next(c for c in self.choices if c.is_correct)


@dataclass
class Scene:
    scene_id: int
    scene_type: str  # narrative | consequence | resolution
    summary: str
    duration_seconds: float
    character_actions: str
    initial_positions: list[dict]
    dialogue: list[DialogueLine]
    sound_effects: str
    ambience: str
    routes_to: dict | None  # verbatim from the script
    setting_override: str = ""  # per-scene setting string, if the dialect has one

    @property
    def routes_to_dp_id(self) -> int | None:
        if self.routes_to and "decision_point_id" in self.routes_to:
            return self.routes_to["decision_point_id"]
        return None

    @property
    def routes_to_scene_id(self) -> int | None:
        if self.routes_to and self.routes_to.get("type") == "scene":
            return self.routes_to.get("scene_id")
        return None


@dataclass
class ScenarioSpec:
    title: str
    learning_goal: str
    target_audience: str
    total_duration_seconds: float
    visual_style: str
    setting: dict
    characters: list[Character]
    scenes: list[Scene]
    decision_points: list[DecisionPoint]
    warnings: list[str] = field(default_factory=list)

    @property
    def scenes_by_id(self) -> dict[int, Scene]:
        return {s.scene_id: s for s in self.scenes}

    @property
    def characters_by_id(self) -> dict[str, Character]:
        return {c.character_id: c for c in self.characters}

    @property
    def branch_scene_ids(self) -> set[int]:
        """Scenes reached via a decision-point choice (consequence/resolution)."""
        return {
            c.routes_to_scene
            for dp in self.decision_points
            for c in dp.choices
            if c.routes_to_scene is not None
        }

    @property
    def trunk_scenes(self) -> list[Scene]:
        """Scenes on the main storyline, in script order."""
        branch_ids = self.branch_scene_ids
        return [s for s in self.scenes if s.scene_id not in branch_ids]


def load_script(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm_dialogue(audio: dict) -> list[DialogueLine]:
    lines = []
    for d in audio.get("dialogue") or []:
        lines.append(
            DialogueLine(
                character_id=d.get("character_id", ""),
                line=d.get("line", ""),
                position=d.get("character_position", "") or "",
            )
        )
    # alternate "clips" dialect (used by the Veo runtime scenario.json)
    for c in audio.get("clips") or []:
        lines.append(
            DialogueLine(
                character_id=c.get("character_id", ""),
                line=c.get("dialogue", ""),
            )
        )
    return [l for l in lines if l.line.strip()]


def _norm_scene(raw: dict) -> Scene:
    audio = raw.get("audio") or {}
    setting = raw.get("setting")
    return Scene(
        scene_id=int(raw["scene_id"]),
        scene_type=(raw.get("type") or raw.get("scene_type") or "narrative")
        .strip()
        .lower(),
        summary=raw.get("scene_summary") or raw.get("description") or "",
        duration_seconds=float(raw.get("duration_seconds") or 0),
        character_actions=raw.get("character_actions", ""),
        initial_positions=raw.get("initial_character_positions") or [],
        dialogue=_norm_dialogue(audio),
        sound_effects=audio.get("sound_effects", ""),
        ambience=audio.get("ambience", ""),
        routes_to=raw.get("routes_to"),
        setting_override=setting if isinstance(setting, str) else "",
    )


def _norm_character(raw: dict, voice: str) -> Character:
    return Character(
        character_id=raw.get("character_id", ""),
        name=raw.get("name", ""),
        role=raw.get("role", ""),
        appearance=raw.get("appearance") or {},
        emotional_baseline=raw.get("emotional_baseline", ""),
        voice=voice,
    )


def _norm_decision_point(raw: dict) -> DecisionPoint:
    choices = [
        Choice(
            choice_id=c.get("choice_id", ""),
            text=c.get("text", ""),
            is_correct=bool(c.get("is_correct")),
            misconception=c.get("misconception"),
            routes_to_scene=c.get("routes_to_scene"),
        )
        for c in raw.get("choices") or []
    ]
    return DecisionPoint(
        decision_point_id=int(raw["decision_point_id"]),
        question_text=raw.get("question_text", ""),
        intro_scene_id=raw.get("associated_introduction_scene_id"),
        choices=choices,
    )


def adapt(script: dict) -> ScenarioSpec:
    """Normalize + validate a script dict. Raises ScriptValidationError with
    every hard problem found; soft problems land in spec.warnings."""
    for key in ("scenes", "characters"):
        if not script.get(key):
            raise ScriptValidationError(f"Script is missing required key: '{key}'")

    characters = [
        _norm_character(c, FALLBACK_VOICES[i % len(FALLBACK_VOICES)])
        for i, c in enumerate(script["characters"])
    ]
    scenes = [_norm_scene(s) for s in script["scenes"]]
    dps = [_norm_decision_point(d) for d in script.get("decision_points") or []]

    spec = ScenarioSpec(
        title=script.get("title", ""),
        learning_goal=script.get("learning_goal", ""),
        target_audience=script.get("target_audience", ""),
        total_duration_seconds=float(script.get("total_duration_seconds") or 0),
        visual_style=script.get("visual_style", ""),
        setting=(
            script.get("setting") if isinstance(script.get("setting"), dict) else {}
        ),
        characters=characters,
        scenes=scenes,
        decision_points=dps,
    )

    errors: list[str] = []
    scene_ids = [s.scene_id for s in scenes]
    if len(scene_ids) != len(set(scene_ids)):
        dupes = sorted({i for i in scene_ids if scene_ids.count(i) > 1})
        errors.append(f"Duplicate scene_ids: {dupes}")
    known_scenes = set(scene_ids)
    known_dps = {dp.decision_point_id for dp in dps}
    known_chars = {c.character_id for c in characters}

    for dp in dps:
        correct = [c for c in dp.choices if c.is_correct]
        if len(correct) != 1:
            errors.append(
                f"Decision point {dp.decision_point_id} has {len(correct)} correct "
                f"choices; exactly one is required"
            )
        if len(dp.choices) - len(correct) < 1:
            spec.warnings.append(
                f"Decision point {dp.decision_point_id} has no incorrect choices"
            )
        for c in dp.choices:
            if c.routes_to_scene is None:
                spec.warnings.append(
                    f"DP {dp.decision_point_id} choice {c.choice_id} has no linked "
                    f"scene; no clip will be generated for it"
                )
            elif c.routes_to_scene not in known_scenes:
                errors.append(
                    f"DP {dp.decision_point_id} choice {c.choice_id} routes to "
                    f"nonexistent scene {c.routes_to_scene}"
                )
            elif not c.is_correct:
                # incorrect choices should loop back to the same decision point
                branch = spec.scenes_by_id.get(c.routes_to_scene)
                if (
                    branch is not None
                    and branch.routes_to_dp_id != dp.decision_point_id
                ):
                    spec.warnings.append(
                        f"Consequence scene {c.routes_to_scene} (DP "
                        f"{dp.decision_point_id} choice {c.choice_id}) does not "
                        f"route back to its decision point"
                    )
        if dp.intro_scene_id is not None and dp.intro_scene_id not in known_scenes:
            errors.append(
                f"DP {dp.decision_point_id} introduction scene "
                f"{dp.intro_scene_id} does not exist"
            )

    for s in scenes:
        dp_id = s.routes_to_dp_id
        if dp_id is not None and dp_id not in known_dps:
            errors.append(
                f"Scene {s.scene_id} routes to nonexistent decision point {dp_id}"
            )
        next_id = s.routes_to_scene_id
        if next_id is not None and next_id not in known_scenes:
            errors.append(f"Scene {s.scene_id} routes to nonexistent scene {next_id}")
        for line in s.dialogue:
            if line.character_id and line.character_id not in known_chars:
                spec.warnings.append(
                    f"Scene {s.scene_id} has dialogue for unknown character "
                    f"'{line.character_id}'; a narrator voice will be used"
                )

    if errors:
        raise ScriptValidationError(
            "Script failed validation:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    return spec
