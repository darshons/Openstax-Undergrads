import json


def validate_scenario(scenario: dict):
    required = ["scenes", "characters", "visual_style"]
    for key in required:
        if key not in scenario:
            raise ValueError(f"Scenario JSON missing required key: '{key}'")


def load_scenario(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    validate_scenario(scenario)
    return scenario
