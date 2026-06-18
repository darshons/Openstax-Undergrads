import json
import tempfile
from pathlib import Path


def process_scene_json(json_script: str, character_image_file_mapping: dict) -> dict:
    data = json.loads(json_script)
    
    scene_file_mapping = {}
    
    PROJECT_DIR = Path(__file__).resolve().parents[1]
    
    dir_path = PROJECT_DIR / "Filtered_JSON_Output"
    
    for scene in data["scenes"]:
        
        scene.pop("routes_to", None)

        scene_json = {
            "visual_style": data["visual_style"],
            "characters": data["characters"],
            "scene": scene,            
        }
        
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            dir=dir_path
        )
        
        with temp_file:
         json.dump(scene_json, temp_file, indent=4)
         
        scene_file_mapping[scene["scene_id"]] = temp_file.name
      
    
    return scene_file_mapping


