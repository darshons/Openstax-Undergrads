import json
import tempfile
from pathlib import Path


def process_background_json(json_script: str) -> str:
    data = json.loads(json_script)
    
    background_file_path = None
    
    PROJECT_DIR = Path(__file__).resolve().parents[1]
    
    dir_path = PROJECT_DIR / "Filtered_JSON_Output"
    
    background_json = {
            "visual_style": data["visual_style"],
            "setting": data["setting"]
            }
        
    temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            dir=dir_path
        )
        
    with temp_file:
        json.dump(background_json, temp_file, indent=4)
        
    background_file_path = temp_file.name
      
    return background_file_path
