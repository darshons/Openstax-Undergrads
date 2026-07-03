import json
import tempfile
from pathlib import Path


# This function creates a temporary JSON file containing the scene information extracted from the provided JSON script. It returns a dictionary mapping scene IDs to the paths of the temporary JSON files.
def process_scene_json(json_script: dict, retry_id: str | None = None) -> dict:

    scene_file_mapping = {}

    dir_path = Path(tempfile.gettempdir()) / "Filtered_JSON_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    scene_fields = ["scene_id", "scene_summary", "initial_character_positions"]

    for scene in json_script["scenes"]:
        # only process the requested scene if retry_id is given
        if retry_id is not None and scene["scene_id"] != int(retry_id):
            continue

        filtered_scene = {key: scene[key] for key in scene_fields}

        scene_json = {
            "visual_style": json_script["visual_style"],
            "setting": json_script["setting"],
            "characters": json_script["characters"],
            "scene": filtered_scene,
        }

        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=dir_path
        )

        with temp_file:
            json.dump(scene_json, temp_file, indent=4)

        scene_file_mapping[scene["scene_id"]] = temp_file.name

        if retry_id is not None:
            break

    return scene_file_mapping
