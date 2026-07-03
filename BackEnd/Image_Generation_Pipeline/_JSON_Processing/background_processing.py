import json
import tempfile
from pathlib import Path


# This function creates a temporary JSON file containing the background information extracted from the provided JSON script. It returns the path to the temporary JSON file.
def process_background_json(json_script: dict) -> str:
    background_file_path = None

    dir_path = Path(tempfile.gettempdir()) / "Filtered_JSON_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    background_json = {
        "visual_style": json_script["visual_style"],
        "setting": json_script["setting"],
    }

    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=dir_path
    )

    with temp_file:
        json.dump(background_json, temp_file, indent=4)

    background_file_path = temp_file.name

    return background_file_path
