import json


def validate_scenario(scenario: dict):
    required = ["scenes", "characters"]
    for key in required:
        if key not in scenario:
            raise ValueError(f"Scenario JSON missing required key: '{key}'")


def load_scenario(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    validate_scenario(scenario)
    return scenario


def get_clip(scenario: dict, scene_id: int, clip_id: int) -> dict:
    """Return {dialogue, characters, setting, character_actions} for one clip:
    its dialogue lines from scenario.json, the full character list of its
    parent scene, and the setting/character_actions used by the physical-
    consistency check (clip-level falls back to scene-level when absent)."""
    scene = next((s for s in scenario["scenes"] if s["scene_id"] == scene_id), None)
    if scene is None:
        raise ValueError(f"No scene found with scene_id={scene_id}")

    clip = next((c for c in scene.get("clips", []) if c["clip_id"] == clip_id), None)
    if clip is None:
        raise ValueError(f"No clip found with clip_id={clip_id} in scene {scene_id}")

    return {
        "dialogue": clip.get("dialogue", []),
        "characters": scenario["characters"],
        "setting": scene.get("setting", ""),
        "character_actions": clip.get(
            "character_actions", scene.get("character_actions", "")
        ),
    }
