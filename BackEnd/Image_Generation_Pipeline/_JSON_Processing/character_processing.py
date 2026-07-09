import json
import tempfile
from pathlib import Path


# This function creates a temporary JSON file containing the character information extracted from the provided JSON script. It returns a dictionary mapping character IDs to the paths of the temporary JSON files.
def process_character_json(
    json_script: dict, retry_image_id: str | None = None
) -> dict[str, str]:
    characters_file_mapping = {}

    dir_path = Path(tempfile.gettempdir()) / "Filtered_JSON_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    for character in json_script["characters"]:
        # only process the requested character if retry_image_id is given
        if retry_image_id is not None and character["character_id"] != retry_image_id:
            continue

        character_json = {
            "visual_style": json_script["visual_style"],
            "character": character,
        }

        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=dir_path
        )

        with temp_file:
            json.dump(character_json, temp_file, indent=4)

        characters_file_mapping[character["character_id"]] = temp_file.name

        if retry_image_id is not None:
            break

    return characters_file_mapping
