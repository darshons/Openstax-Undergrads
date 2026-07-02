from .._JSON_Processing import process_scene_json
from google import genai
from google.genai import types
from Script_Generation_Pipeline import setup_gemini_client
from PIL import Image
from io import BytesIO
from pathlib import Path
import tempfile


# This function generates opening frame images for each scene in the provided JSON script, using character and background reference images. It returns a mapping of scene IDs to generated opening frame image file paths, a list of uploaded file names for cleanup, and a list of local JSON file paths for cleanup.
def generate_opening_frames(
    json_script,
    character_image_file_mapping,
    background_image_file_path,
    request_id,
    scene_id: str | None = None,
) -> tuple[dict[str, str], list[str | None], list[str]]:
    # Set up Gemini client
    client = setup_gemini_client()

    # Define system prompts for opening and ending frame generation
    opening_frame_system_prompt = """
    You are generating an opening scene image for an interactive training simulation.

    Your task is to create exactly one high-quality still image that represents the very beginning of the scene described in the provided JSON input.  

    The purpose of this image is to serve as the scene's opening frame. It should depict the initial situation before any significant actions, decisions, outcomes, or scene developments have occurred. The image should establish the setting, participants, and relevant context that a learner would observe when the scene first begins.

    The user prompt will provide:
    • Character reference images that define the appearance of all characters.
    • Background reference image that defines the appearance of all relevant environmental elements.
    • A JSON object detailing the scene description and character information. 

    The JSON object will have the following structure:
    
    
{
        "visual_style": "",
          "setting": {
        "location": "",
        "scene_description": "",
        "light_source": "", 
        "time_of_day": "",
        "atmosphere": "",
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
    },
    "characters": [
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
    ],
    "scene": 
        {
        "scene_id": 1,
        "scene_summary": "",
        "initial_character_positions": [{
        "character_id": "",
        "position": ""
      }]
    }
}
  
    Image Generation Instructions:
    • Generate exactly one image.
    • Depict only the opening moment of the scene.
    • The image should represent the earliest point in time that can reasonably be inferred from the scene description.
    • Focus on establishing the initial conditions of the scenario rather than later events, consequences, or developments.
    • Do not depict future actions, outcomes, or information that would not yet be visible at the start of the scene.
    • Use the `visual_style` field to determine the artistic style, realism level, rendering quality, and overall visual presentation.
    • Include all important characters, objects, and environmental details that would be visible at the beginning of the scene.
    • Focus exclusively on visual content. 
    • Do not include dialogue, narration, captions, subtitles, labels, or text within the image under any circumstances.
    • Ensure the image clearly establishes who is present, where the scene takes place, and what situation is unfolding at the start of the scenario.
    
   Reference Image Fidelity Requirements:
    • The character reference images are the definitive source of truth for character identity and appearance. Do not redesign, reinterpret, embellish, or alter the characters.
    • Reproduce each referenced character with maximum possible visual fidelity, preserving facial structure, facial proportions, eye shape, nose shape, mouth shape, hairstyle, hair color, skin tone, age, body type, clothing, accessories, and all other visible identifying characteristics.
    • Maintain identity-level consistency with the reference images. The generated character should be immediately recognizable as the exact same individual depicted in the references.
    • Any ambiguity in the character description must be resolved in favor of preserving the appearance shown in the character reference images.
    • Do not substitute, simplify, stylize, average, or invent character features that are not supported by the character reference images.
    • Ensure that facial identity remains highly consistent even when the character is viewed from different angles, distances, poses, lighting conditions, or expressions.
    • The success of the image is determined primarily by how accurately the characters match their reference images. Character identity preservation is more important than artistic style, dramatic composition, or visual effects.
    • Before finalizing the image, verify that every referenced character closely matches their reference images and their descriptions in the JSON scene description under the `characters` field, such that no significant visual deviations have been introduced to the characters.

    Background Reference Fidelity Requirements:
    • The background reference image is the definitive source of truth for the environment, location, architecture, layout, furnishings, props, materials, colors, and all other visible environmental elements. Do not redesign, reinterpret, embellish, or substantially alter the setting depicted in the reference image.
    • Reproduce the environment with maximum possible visual fidelity, preserving the overall spatial layout, architectural features, room configuration, structural elements, furniture placement, surface materials, textures, color palette, décor, signage, equipment, and other visible environmental details.
    • Maintain scene-level consistency with the background reference image. The generated setting should be immediately recognizable as the same location depicted in the reference image.
    • Any ambiguity in the scene description must be resolved in favor of preserving the environment shown in the background reference image
    • Do not substitute, simplify, stylize, remove, or invent major environmental features that are not supported by the background reference image.
    • Preserve the relative positioning and visual relationships between important environmental elements whenever they are visible in the generated composition.
    • Ensure that environmental details remain consistent even when viewed from different camera angles, focal lengths, distances, or compositions.
    • Before finalizing the image, verify that the environment closely matches the background reference image  and their descriptions in the JSON scene description under the `setting` field, such that no significant architectural, spatial, stylistic, or environmental deviations have been introduced.
     • Use the `background_furniture` and `background_equipment` fields in the JSON scene description to ensure that all relevant furniture and equipment are accurately represented in the opening frame image.


    The resulting image should function as an establishing shot for the scenario, providing a clear visual introduction to the scene and its initial state before the main events occur.
    """
    # Define the model to use for image generation
    MODEL = "gemini-3.1-flash-image"

    # Configure content generation settings for opening and ending frames
    opening_frame_config = types.GenerateContentConfig(
        system_instruction=opening_frame_system_prompt,
        response_modalities=["IMAGE"],
    )

    # Process the JSON to create individual JSON files for each scene -> Mapping of scene_id to local JSON file path
    scene_json_file_mapping = process_scene_json(
        json_script, character_image_file_mapping, scene_id=scene_id
    )

    # Path setup for saving generated images
    dir_path = Path(tempfile.gettempdir()) / "Frame_Image_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    # Mapping to keep track of uploaded character images (character_id to uploaded file name and file object)
    uploaded_character_image_mapping = {}

    # Mapping to keep track of uploaded scene JSON files (scene_id to uploaded file name and file object)
    uploaded_scene_json_mapping = {}

    # Mappings to keep track of generated opening and ending frame file paths (scene_id to local file path)
    opening_scene_frame_file_mapping = {}

    # Upload the background reference image to Gemini and store its uploaded file name for reference in prompts
    uploaded_background_image = client.files.upload(
        file=background_image_file_path,
        config=types.UploadFileConfig(
            display_name="background_reference_image", mime_type="image/png"
        ),
    )

    # Upload character reference images and scene JSON files to Gemini and store their uploaded file names for reference in prompts
    for character_id, character_image_file_path in character_image_file_mapping.items():

        uploaded_character_image = client.files.upload(
            file=character_image_file_path,
            config=types.UploadFileConfig(
                display_name=f"character_reference_image_{character_id}",
                mime_type="image/png",
            ),
        )

        uploaded_character_image_mapping[character_id] = (
            uploaded_character_image.name,
            uploaded_character_image,
        )

    for scene_id, scene_json_file_path in scene_json_file_mapping.items():

        uploaded_json = client.files.upload(
            file=scene_json_file_path,
            config=types.UploadFileConfig(
                display_name=f"scene_description_{scene_id}",
                mime_type="application/json",
            ),
        )

        uploaded_scene_json_mapping[scene_id] = (uploaded_json.name, uploaded_json)

    uploaded_file_names = (
        [
            uploaded_json_name
            for uploaded_json_name, _ in uploaded_scene_json_mapping.values()
        ]
        + [
            uploaded_character_image_name
            for uploaded_character_image_name, _ in uploaded_character_image_mapping.values()
        ]
        + [uploaded_background_image.name]
    )

    # For each scene, the opening and ending frame generation prompts will reference the corresponding uploaded JSON file and all uploaded character reference images to ensure the generated frames are consistent with the scene description and character appearances.
    character_references = "\n".join(
        f"- Character ID {character_id}: uploaded image file {uploaded_file_name}"
        for character_id, (
            uploaded_file_name,
            _,
        ) in uploaded_character_image_mapping.items()
    )

    for scene_id, (
        uploaded_json_name,
        uploaded_json,
    ) in uploaded_scene_json_mapping.items():

        # OPENING FRAME GENERATION
        opening_frame_user_query = f"""
        Generate an opening scene frame image based on the uploaded JSON file:

        Scene JSON:
        {uploaded_json_name}

        Character reference images:
        {character_references}
        
        Background reference image:
        {uploaded_background_image.name}
        """

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                opening_frame_user_query,
                uploaded_json,
                *[
                    uploaded_character_image
                    for _, uploaded_character_image in uploaded_character_image_mapping.values()
                ],
                uploaded_background_image,
            ],
            config=opening_frame_config,
        )

        if (
            not response.candidates
            or not response.candidates[0]
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            return (
                opening_scene_frame_file_mapping,
                uploaded_file_names,
                list(scene_json_file_mapping.values()),
            )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(dir_path / f"{request_id}_{scene_id}_opening_frame.png")

        opening_scene_frame_file_mapping[scene_id] = str(
            dir_path / f"{request_id}_{scene_id}_opening_frame.png"
        )

    return (
        opening_scene_frame_file_mapping,
        uploaded_file_names,
        list(scene_json_file_mapping.values()),
    )
