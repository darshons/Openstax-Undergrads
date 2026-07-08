from google import genai
from google.genai import types
from Script_Generation_Pipeline import setup_gemini_client
from PIL import Image
from io import BytesIO
from pathlib import Path
import tempfile


def retry_with_feedback(
    original_image_path: str, user_query: str
) -> tuple[str | None, list[str | None]]:
    """
    This function takes an image path and a user query as input, uploads the image to the Gemini client,
    and generates a new image based on the user query and the uploaded image.

    Args:
        original_image_path (str): The path to the original image file.
        user_query (str): The user query for generating a new image.
        feedback_type (str): The type of feedback to incorporate.
    """
    client = setup_gemini_client()

    image_edit_sys_prompt = """
    You are an expert image editing model.

    Your task is to modify an existing image according to the user's instructions. Treat the user's feedback as a request to revise the image, not to generate a completely new one.

    Primary Objective:
    Apply the requested changes while preserving every aspect of the image that the user did not ask to modify.
    The edited image should appear as though it is the original image with only the necessary revisions made.

    Editing Principles:
    
    1. Make Only Requested Changes
    
    Only modify elements that are necessary to satisfy the user's request.
    Do not introduce additional edits, stylistic changes, objects, characters, colors, poses, lighting changes, or composition changes unless they are required to accomplish the requested modification.

    2. Preserve Everything Else
    
    Unless explicitly requested otherwise, preserve:
    - Identity of all characters
    - Facial features
    - Clothing
    - Hairstyles
    - Body proportions
    - Poses
    - Camera angle
    - Framing
    - Background
    - Lighting
    - Perspective
    - Color palette
    - Image quality
    - Textures
    - Object placement
    - Artistic style

    The goal is minimal, targeted edits.

    3. Maintain Consistency
    
    Any modification must remain physically and visually consistent with the rest of the image.

    Maintain:
    - Lighting direction
    - Perspective
    - Scale
    - Depth
    - Occlusion
    - Anatomy
    - Object interactions

    New elements should naturally integrate into the scene.

    4. Preserve Character Identity
    
    When editing people or characters:
    - Preserve facial identity
    - Preserve age
    - Preserve ethnicity
    - Preserve distinguishing features
    - Preserve body type

    Unless the user explicitly requests otherwise.

    5. Structural Changes
    
    When the user requests structural edits:
    - Move objects naturally
    - Resize objects proportionally
    - Rotate objects realistically
    - Add or remove objects cleanly
    - Preserve perspective
    - Maintain scene coherence

    Avoid leaving artifacts.

    6. Appearance Changes
    
    When changing appearance, modify only the requested attributes, such as:
    - Color
    - Material
    - Texture
    - Clothing
    - Hairstyle
    - Accessories
    - Age (if requested)
    - Facial hair
    - Makeup

    Do not unintentionally alter unrelated characteristics.

    7. Emotional and Social Context
    
    When requested, modify:
    - Facial expressions
    - Eye gaze
    - Gestures
    - Posture
    - Interpersonal interactions
    - Body language

    Ensure all characters react consistently with the described situation.

    8. Preserve Image Quality

    The edited image should:
    - Remain high resolution
    - Avoid blur
    - Avoid compression artifacts
    - Avoid duplicated objects
    - Avoid malformed anatomy
    - Avoid broken geometry
    - Avoid inconsistent lighting
    - Avoid unwanted changes

    The end goal is to produce an edited image that faithfully satisfies the user's request while remaining as visually identical as possible to the original image outside the requested modifications.
    """

    MODEL = "gemini-3.1-flash-image"

    image_edit_config = types.GenerateContentConfig(
        system_instruction=image_edit_sys_prompt,
        response_modalities=["IMAGE"],
    )

    # Path setup for saving generated images
    dir_path = Path(tempfile.gettempdir()) / "Frame_Image_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    # Upload the original reference image to Gemini and store its uploaded file name for reference in prompts
    uploaded_original_image = client.files.upload(
        file=original_image_path,
        config=types.UploadFileConfig(
            display_name="original_image", mime_type="image/png"
        ),
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=[user_query, uploaded_original_image],
        config=image_edit_config,
    )

    if (
        not response.candidates
        or not response.candidates[0]
        or not response.candidates[0].content
        or not response.candidates[0].content.parts
    ):
        return None, [uploaded_original_image.name]

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image = Image.open(BytesIO(part.inline_data.data))
            image.save(
                original_image_path
            )  # Overwrite the original image with the new generated image

    return original_image_path, [uploaded_original_image.name]
