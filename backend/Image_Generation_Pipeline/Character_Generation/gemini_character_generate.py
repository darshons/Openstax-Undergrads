from Image_Generation_Pipeline.JSON_Processing.character_processing import process_character_json
from google import genai
from google.genai import types
from Script_Generation_Pipeline.Script_With_Dpoints.gemini_script_generation import setup_gemini_client
from PIL import Image
from io import BytesIO
from pathlib import Path
import os
import json

def generate_characters(json_script) -> tuple[list[Path], list[str], list[Path]]:
    client = setup_gemini_client()
    
    system_prompt = """
    You are generating a character visual asset for an interactive training simulation.

    This simulation presents learners with branching scenarios in which they observe situations, analyze information, and make decisions at key moments. To support visual consistency throughout the simulation, your task is to generate a high-quality character reference image for the character object provided in the input JSON, establishing the definitive appearance of that character.

    Based on the character description below, generate a comprehensive visual character asset that clearly establishes:
    • Facial features and overall appearance
    • Body type, age range, and physical characteristics
    • Hairstyle, hair color, and grooming details
    • Clothing, accessories, uniforms, and equipment
    • Typical posture and demeanor
    • Distinguishing visual traits that help identify the character

    The generated asset should function as an authoritative reference material for all future scene generation. The character's appearance must be clearly defined, unambiguous, and visually consistent across all views, poses, expressions, and future depictions.

    Focus exclusively on visual appearance. Do not generate dialogue, narration, backstory, or personality descriptions beyond what is visually observable.

    The asset should be realistic, professional, and instructional in tone. Avoid exaggerated, stylized, fantasy, or entertainment-focused character designs unless explicitly requested.

    The user prompt will provide a JSON object with the following structure:

    {
    "visual_style": "",
    "character": 
        {
        "character_id": "",
        "name": "",
        "role": "",
        "appearance": {
            "skin_tone": "",
            "hair": "",
            "build": "",
            "uniform": "",
            "distinguishing_features": ""
        },
        "emotional_baseline": ""
        }
    }

    Use the "visual_style" field as the global visual specification for the generated asset.
    
    The "character" object represents the single character to be generated.
    
    Image Generation Requirements:
    • Generate exactly one image.
    • The image must contain only the specified character.
    • Use all provided character fields when constructing the visual appearance.
    • Maintain the specified visual style throughout the asset.
    • No text should appear in the image other than the character's name (included once in the top left corner of the image). Do not include captions, labels, or extraneous text.
    • The background should be a simple, neutral solid color (e.g., white, beige, or light gray) that does not distract from the character. Avoid complex backgrounds, patterns, scenery, as well as any borders, frames, grids, or dividing lines; the character should appear cleanly presented without visual boundaries.
    • Show the character from exactly five views within a single image to provide a complete reference set: 1 front view, 2 side views (45 degrees), 1 back view, and 1 dedicated close-up of the face to clearly capture facial features and identity. Do not add additional views, poses, or expressions beyond these specified angles.
    • Ensure that there is no overlapping, cropping, or visual obstruction of the character in any of the views. The character should be fully visible and clearly distinguishable in each view.
    
    Your output should create a clear, production-ready character reference asset that can be used consistently throughout the simulation.
    """
    
    MODEL = "gemini-3.1-flash-image"
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_modalities=["IMAGE"],    
    )
    
    characters_file_mapping = process_character_json(json_script)
        
    PROJECT_DIR = Path(__file__).resolve().parents[1]
    
    dir_path = PROJECT_DIR / "Character_Image_Output"
    
    uploaded_json_file_names = []
    
    json_file_paths = []
    
    character_image_paths = []
    
    for character_id, character_json_path in characters_file_mapping.items():
    
        uploaded_json = client.files.upload(file=character_json_path, config=types.UploadFileConfig(display_name=f"character_description_{character_id}", mime_type="application/json"))
        
        user_query = f"Generate a character reference image based on the character description in the uploaded JSON file: {uploaded_json.name} for character ID {character_id}."
        
        response = client.models.generate_content(
            model=MODEL,
            contents=[user_query, uploaded_json],
            config=config
        )
        
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(dir_path / f"{character_id}_reference_image.png")
                
        uploaded_json_file_names.append(uploaded_json.name)
        
        json_file_paths.append(character_json_path)
        
        character_image_paths.append(dir_path / f"{character_id}_reference_image.png")
        
    return character_image_paths, uploaded_json_file_names, json_file_paths

def delete_json_files(file_paths):
    for file_path in file_paths:
        os.remove(file_path)
        
def delete_uploaded_json_files(client, file_names):
    for file in file_names:
        client.files.delete(name=file)

if __name__ == "__main__":
    json_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/BackEnd/Script_Generation_Pipeline/Script_Outputs/output_script_without_decision_points_gemini.json"

    
    with open(json_file_path, "r") as f:
        json_script = f.read()
        
    character_image_paths, uploaded_json_file_names, json_file_paths = generate_characters(json_script)
    
    delete_json_files(json_file_paths)
    
    delete_uploaded_json_files(setup_gemini_client(), uploaded_json_file_names)
    
    
    
#     from dotenv import load_dotenv
# from pathlib import Path
# from google import genai
# import os


# env_path = Path(__file__).resolve().parents[2] / "backend.env"
# load_dotenv(env_path)
# client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# # List all uploaded files
# for file in client.files.list():
#     print(f"Display Name: {file.display_name}")
#     print(f"  File ID: {file.name}") # Will look like 'files/abc123xyz...'
#     print(f"  Mime Type:    {file.mime_type}")
#     print(f"  URI:          {file.uri}")
#     # client.files.delete(name=file.name)
