from .._JSON_Processing import process_background_json
from google import genai
from google.genai import types
from Script_Generation_Pipeline import setup_gemini_client
from PIL import Image
from io import BytesIO
from pathlib import Path
import tempfile


# This function generates a background reference image based on the provided JSON script.
def generate_background(
    json_script, request_id
) -> tuple[str | None, list[str | None], list[str]]:
    client = setup_gemini_client()

    system_prompt = """
    You are generating a background visual asset for an interactive training simulation.
    
    This simulation presents learners with branching scenarios in which they observe environments, interpret contextual cues, and make decisions based on situational awareness. To ensure visual consistency across all scenes, your task is to generate a high-quality environment reference image for the setting object provided in the input JSON, establishing the definitive appearance of the location.
    
    Based on the setting description below, generate a comprehensive visual environment asset that clearly establishes:
    • Overall layout and spatial composition of the environment
    • Furniture, objects, and environmental props
    • Lighting design, including source, intensity, color, and direction
    • Time of day and lighting conditions
    • Materials, textures, and surface details
    • Distinguishing environmental features that make the setting identifiable

    The generated asset should function as an authoritative reference for all future scene generation. The environment's appearance must be clearly defined, unambiguous, and visually consistent across all future depictions, camera angles, and scene uses.

    Focus exclusively on visual appearance. Do not generate narrative, dialogue, characters, or story context beyond what is visually observable.

    The asset should be realistic, professional, and instructional in tone. Avoid exaggerated, fantastical, or stylized environments unless explicitly requested.
    
    The user prompt will provide a JSON object with the following structure:

{
    "visual_style": "",
       "setting": {
    "location": "",
    "scene_description": "",
    "light_source": "",
    "time_of_day": "",
    "atmosphere": "",
    "background_furniture": [
    {
      "name": "",
      "count": 0,
      "description": ""
    }
  ],
    "background_equipment": [
      {
        "name": "",
        "count": 0,
        "description": ""
      }
    ],
     "camera": {
      "angle": "",
      "perspective": ""
    }
  }
}

    Use the "visual_style" field as the global visual specification for the generated asset.
    
    The "setting" object represents the single environment to be generated.
    
    Use the "background_furniture" and "background_equipment" fields in the JSON scene description to ensure that all relevant furniture and equipment are accurately represented in the background reference image.
    
    Image Generation Requirements:
    • Generate exactly one image.
    • The image must contain only the specified environment.
    • Use all provided setting fields when constructing the scene.
    • Maintain the specified visual style throughout the asset.
    • No text should appear in the image.
    • No characters, people, animals, or living subjects should appear in the image whatsoever.
    • The background should represent a complete, coherent environment with natural spatial depth and perspective.
    
    Your output should create a clear, production-ready background reference asset that can be used consistently throughout the simulation.

    """

    MODEL = "gemini-3.1-flash-image"

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_modalities=["IMAGE"],
    )

    background_image_file_path = None

    background_json_path = process_background_json(json_script)

    dir_path = Path(tempfile.gettempdir()) / "Background_Image_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    uploaded_json = client.files.upload(
        file=background_json_path,
        config=types.UploadFileConfig(
            display_name=f"background_description", mime_type="application/json"
        ),
    )

    user_query = f"Generate a background reference image based on the background description in the uploaded JSON file: {uploaded_json.name}."

    response = client.models.generate_content(
        model=MODEL, contents=[user_query, uploaded_json], config=config
    )

    if (
        not response.candidates
        or not response.candidates[0]
        or not response.candidates[0].content
        or not response.candidates[0].content.parts
    ):
        return background_image_file_path, [uploaded_json.name], [background_json_path]

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image = Image.open(BytesIO(part.inline_data.data))
            background_image_file_path = str(
                dir_path / f"{request_id}_background_reference_image.png"
            )
            image.save(background_image_file_path)

    return background_image_file_path, [uploaded_json.name], [background_json_path]
