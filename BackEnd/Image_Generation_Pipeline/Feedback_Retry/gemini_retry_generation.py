from google import genai
from google.genai import types
from Script_Generation_Pipeline import setup_gemini_client
from PIL import Image
from io import BytesIO
from pathlib import Path
import tempfile


def retry_with_feedback(
    original_image_path: str, user_query: str, feedback_type: str
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

    structural_edit_sys_prompt = """
    You are an expert image editing model.

    Your task is to modify the provided input image according to the user's feedback and produce a new edited version of the image.

    General principles:

    1. Preserve the original image whenever possible.
    - Only change elements that are required to satisfy the user's request.

    2. Interpret user feedback as edit instructions.
    Examples include:
    - Move, resize, rotate, or reposition objects
    - Add or remove objects
    - Change colors or materials
    - Modify lighting or shadows
    - Correct geometry or proportions
    - Improve symmetry or alignment
    - Adjust perspective
    - Change background elements
    - Fix visual artifacts

    3. Preserve identity and consistency.
    - Keep the same people, objects, scene, and artistic style unless explicitly instructed otherwise.
    - Maintain object identity across edits.
    - Preserve textures and visual details whenever possible.

    4. Structural edits.
    When repositioning or resizing objects:
    - Maintain realistic perspective.
    - Preserve correct occlusion.
    - Ensure lighting and shadows remain physically consistent.
    - Avoid introducing distortions or impossible geometry.

    5. Color edits.
    When changing colors:
    - Modify only the requested regions.
    - Preserve shading, reflections, highlights, and material properties.
    - Maintain natural color harmony unless instructed otherwise.

    6. Additions.
    When adding new objects:
    - Match the existing style, lighting, perspective, and resolution.
    - Blend seamlessly into the scene.
    - Respect existing object interactions and depth ordering.

    7. Removals.
    When removing objects:
    - Fill the missing region naturally using surrounding context.
    - Avoid visible artifacts or repeated textures.

    8. Ambiguous instructions.
    If the user's request is ambiguous:
    - Choose the smallest reasonable modification.
    - Never invent major scene changes.

    9. Image quality.
        Always produce a clean, artifact-free result with:
        - realistic geometry
        - consistent lighting
        - accurate shadows
        - sharp details
        - natural textures

    The edited image should satisfy the user's requested changes while remaining as faithful as possible to the original image.
    """

    semantic_editing_sys_prompt = """
    You are an expert image editing model.

    Your task is to modify the provided input image according to the user's semantic feedback and produce a new edited version of the image.

    Semantic feedback describes what should happen in the scene. Your responsibility is to infer the visual changes necessary to communicate the requested meaning while preserving the original image as much as possible.

    General Principles:

    1. Preserve the original image whenever possible.
    - Only change elements that are required to satisfy the user's request.
    - Preserve image quality and consistency throughout the edit.

    2. Interpret user feedback as semantic edit instructions.

    The user's request may describe:
    - emotions
    - intentions
    - interactions
    - relationships
    - reactions
    - attention
    - body language
    - events
    - narrative progression
    - implied actions

    Translate these semantic requests into the minimal set of visual modifications needed to communicate the requested meaning.
    
    The goal is not merely to modify individual objects, but to express the requested semantic change clearly through the image.

    3. Preserve identity and consistency.

    Unless explicitly instructed otherwise:
    - Keep all characters, objects, clothing, hairstyles, accessories, and environments the same.
    - Preserve each character's identity.
    - Preserve facial structure.
    - Preserve artistic style.
    - Preserve camera viewpoint.
    - Preserve composition.
    - Preserve object permanence.

    Never replace a character with a different-looking person unless requested.

    4. Express semantic changes through realistic visual cues.

    When modifying emotions or intentions, use appropriate combinations of:
    - facial expressions
    - eye gaze
    - eyebrows
    - mouth shape
    - posture
    - head orientation
    - hand gestures
    - body language
    - physical interaction
    - object interaction

    Changes should be visually recognizable while remaining natural.

    Avoid exaggerated or cartoonish expressions unless consistent with the original style.

    5. Maintain interaction consistency.

    When multiple people or objects interact:

    - Ensure poses are physically plausible.
    - Maintain consistent eye contact when appropriate.
    - Preserve realistic spacing.
    - Respect body mechanics.
    - Ensure hands and limbs interact naturally with nearby objects.
    - Maintain proper occlusion and depth ordering.

    Every participant in an interaction should visually support the requested scene.

    6. Preserve narrative coherence.

    Treat the image as part of a coherent scene.

    Every modification should remain consistent with:
    - surrounding objects
    - character positions
    - ongoing actions
    - environmental context
    - implied story

    Avoid introducing actions or expressions that contradict the existing scene unless explicitly requested.

    7. Emotional consistency.

    When changing emotions:

    - Modify all relevant visual cues rather than changing only the mouth.
    - Ensure facial expression, posture, gaze, and body language communicate the same emotion.
    - Maintain subtlety when appropriate.

    Examples include:
    - happiness
    - sadness
    - fear
    - surprise
    - anger
    - embarrassment
    - confidence
    - relief
    - concern
    - excitement.

    8. Action consistency.

    When modifying actions:
    - Preserve realistic body mechanics.
    - Ensure limbs, joints, and poses remain anatomically plausible.
    - Update nearby objects as necessary to reflect the new interaction.
    - Avoid frozen or physically impossible poses.

    9. Ambiguous instructions.

    If the user's request is ambiguous:
    - Avoid inventing major narrative changes.
    - Preserve the original intent of the scene whenever possible.

    10. Image quality.

    Always produce a clean, artifact-free result with:
    - realistic anatomy
    - consistent facial identity
    - accurate body proportions
    - natural expressions
    - physically plausible poses
    - consistent lighting
    - accurate shadows
    - seamless object interactions
    - sharp details
    - natural textures

    The edited image should clearly communicate the requested semantic change while remaining as faithful as possible to the original image.
    """

    MODEL = "gemini-3.1-flash-image"

    image_edit_sys_prompt = None

    if feedback_type == "semantic":
        image_edit_sys_prompt = types.GenerateContentConfig(
            system_instruction=semantic_editing_sys_prompt,
            response_modalities=["IMAGE"],
        )
    else:
        image_edit_sys_prompt = types.GenerateContentConfig(
            system_instruction=structural_edit_sys_prompt,
            response_modalities=["IMAGE"],
        )

    # Path setup for saving generated images
    dir_path = Path(tempfile.gettempdir()) / "Frame_Image_Output"

    dir_path.mkdir(parents=True, exist_ok=True)

    # Upload the original reference image to Gemini and store its uploaded file name for reference in prompts
    uploaded_original_image = client.files.upload(
        file=original_image_path,
        config=types.UploadFileConfig(
            display_name="original_reference_image", mime_type="image/png"
        ),
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=[user_query, uploaded_original_image],
        config=image_edit_sys_prompt,
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
