import json
import tempfile
from pathlib import Path


def process_character_json(json_script: str) -> dict:
    data = json.loads(json_script)
    
    characters_file_mapping = {}
    
    PROJECT_DIR = Path(__file__).resolve().parents[1]
    
    dir_path = PROJECT_DIR / "Filtered_JSON_Output"
    
    for character in data["characters"]:
        character_json = {
            "visual_style": data["visual_style"],
            "character": character
        }
        
        temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        dir=dir_path
        )
        
        with temp_file:
         json.dump(character_json, temp_file, indent=4)
         
        characters_file_mapping[character["character_id"]] = temp_file.name
    
    return characters_file_mapping