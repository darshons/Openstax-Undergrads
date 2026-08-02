"""Per-scene renderer selection.

A scenario normally mixes two renderers: character animation for scenes that
turn on what a person says or decides, and Manim for scenes that turn on an
equation, a diagram or a quantity. The script generator picks one per scene
(see the "Per-Scene Renderer Selection" block in prompt_assembly.py); this
module is the guarantee that whatever comes back is usable.

Kept free of FastAPI and of the generation dependencies so it can be tested
on its own.
"""

RENDER_MODES = ("scenario", "manim")

# Cues that a scene's meaning lives in something drawn rather than something
# said. The character renderer cannot produce legible text, so any of these
# is enough to route the scene to Manim.
_GRAPHIC_CUES = (
    "equation", "formula", "diagram", "graph", "chart", "table",
    "molecule", "structure", "calculate", "calculation", "ratio", "percent",
    "timeline", "step-by-step", "labelled", "labeled", "axis", "axes",
    "plot", "curve", "vector", "coordinate",
)


def infer_render_mode(scene: dict) -> str:
    """Fallback for when the model left render_mode blank or wrote something odd."""
    text = " ".join(
        str(scene.get(key, "")) for key in ("scene_summary", "character_actions")
    ).lower()
    return "manim" if any(cue in text for cue in _GRAPHIC_CUES) else "scenario"


def normalize_render_modes(script: dict, video_type: str | None) -> dict:
    """Guarantee every scene carries a valid render_mode. Mutates and returns `script`.

    `video_type` of "scenario" or "manim" pins the whole scenario to one
    renderer; anything else (including "auto" and None) keeps the model's
    per-scene choice. Downstream renderers can then read scene["render_mode"]
    unconditionally instead of re-deriving intent.
    """
    forced = video_type if video_type in RENDER_MODES else None

    for scene in (script or {}).get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        if forced:
            scene["render_mode"] = forced
            continue
        mode = str(scene.get("render_mode", "")).strip().lower()
        scene["render_mode"] = mode if mode in RENDER_MODES else infer_render_mode(scene)

    return script
