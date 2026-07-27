from io import BytesIO
from pathlib import Path

from google.genai import types
from PIL import Image as PILImage

from video_generator.prompt_builder import build_character_block, build_dialogue_block

IMAGE_MODEL = "gemini-3.1-flash-image"
PROMPT_WRITER_MODEL = "gemini-2.5-flash"

# Character/background reference images, same assets used by video_generator's
# REFERENCE_IMAGES for cross-clip character consistency.
REFERENCE_IMAGE_PATHS = [
    "reference_images/maya.png",
    "reference_images/carl.png",
]

FIRST_FRAME_SYSTEM_PROMPT = """
You are generating a single still frame for a short animated training video clip.

Your task is to create exactly one high-quality image depicting the state of the
scene at the very START of the described clip — before any of the clip's actions
or dialogue have happened.

The user prompt will provide the visual style, character descriptions, setting,
character actions for the clip, camera framing, and dialogue. Reference images for
each character are also provided as inline images.

Reference Image Fidelity Requirements:
- The character reference images are the definitive source of truth for character
  identity and appearance. Reproduce each character with maximum fidelity: facial
  structure, hairstyle, hair color, skin tone, body type, clothing, and accessories
  must exactly match the references. Do not redesign or reinterpret any character.
- Maintain identity-level and scene-level consistency with the references at all
  times, regardless of camera angle or character pose.

Image Generation Instructions:
- Generate exactly one image.
- Depict only the earliest moment of the clip, before its described actions unfold.
- Use the visual_style description to set the artistic style and rendering quality.
- Do not include dialogue, captions, subtitles, or any text in the image.
- Do not introduce any characters not named in the prompt.
""".strip()

LAST_FRAME_SYSTEM_PROMPT = """
You are generating a single still frame for a short animated training video clip.

Your task is to create exactly one high-quality image depicting the state of the
scene at the very END of the described clip — after the clip's actions and
dialogue have played out. If the character actions describe a gesture, motion, or
posture shift that is still "in progress" or "not yet complete" as the clip ends,
depict that exact in-progress moment — not a fully settled/resolved pose.

The user prompt will provide the visual style, character descriptions, setting,
character actions for the clip, camera framing, and dialogue. Reference images for
each character are also provided as inline images. If a "clip
start" image is also provided, it depicts the same clip's opening frame — use it as
the anchor for continuity (same character positions/environment as a starting
point), and depict where the described actions leave the characters by the end of
the clip.

Reference Image Fidelity Requirements:
- The character reference images are the definitive source of truth for character
  identity and appearance. Reproduce each character with maximum fidelity: facial
  structure, hairstyle, hair color, skin tone, body type, clothing, and accessories
  must exactly match the references. Do not redesign or reinterpret any character.
- Maintain identity-level and scene-level consistency with the references at all
  times, regardless of camera angle or character pose.

Image Generation Instructions:
- Generate exactly one image.
- Depict the state of the scene at the end of the clip's described actions.
- Use the visual_style description to set the artistic style and rendering quality.
- Do not include dialogue, captions, subtitles, or any text in the image.
- Do not introduce any characters not named in the prompt.
""".strip()


_FRAME_PROMPT_SHARED_RULES = """
- State explicitly, for every character named in the input, whether they are
  actually visible on-screen at this exact moment — do not assume a character is
  present just because they're named in the scene's character list or dialogue.
- Resolve entering/exiting/off-frame language literally: a character described as
  "entering" is not yet fully in frame — they may be partially visible from one
  side, or not visible at all yet, depending on the camera framing. A character
  who has "left" or has not yet arrived must be omitted entirely.
- For each character who IS visible, describe their exact pose, position, and
  action at this instant.
- Describe the camera framing (angle, shot type, what's in view).
- Do not invent details — such as extra characters, props, or actions — that
  aren't supported by the input text.
- Output ONLY the descriptive visual prompt itself. No preamble, no labels, no
  JSON, no explanation of your reasoning.
""".strip()

FIRST_FRAME_PROMPT_WRITER_INSTRUCTION = f"""
You are writing a precise visual description for a still-image generation model,
based on a structured description of a video clip's opening moment.

Describe EXACTLY what should be visible at the very START of the clip — before
any of the clip's described actions or dialogue have happened.

{_FRAME_PROMPT_SHARED_RULES}
""".strip()

LAST_FRAME_PROMPT_WRITER_INSTRUCTION = f"""
You are writing a precise visual description for a still-image generation model,
based on a structured description of a video clip.

Describe EXACTLY what should be visible at the very END of the clip — after the
clip's described actions and dialogue have played out. If an action is described
as still "in progress" or "not yet complete" as the clip ends, describe that exact
in-progress moment, not a fully settled/resolved pose.

{_FRAME_PROMPT_SHARED_RULES}
""".strip()


def _write_frame_visual_prompt(client, context_text: str, is_first_frame: bool) -> str:
    system_instruction = (
        FIRST_FRAME_PROMPT_WRITER_INSTRUCTION if is_first_frame else LAST_FRAME_PROMPT_WRITER_INSTRUCTION
    )
    response = client.models.generate_content(
        model=PROMPT_WRITER_MODEL,
        contents=[context_text],
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    if not response.text:
        raise RuntimeError("Prompt-writer model returned no text.")
    return response.text.strip()


def _load_image_parts(image_paths: list) -> list:
    parts = []
    for path in image_paths:
        with open(path, "rb") as f:
            image_bytes = f.read()
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
    return parts


def _clip_context_text(scene: dict, clip: dict, characters: list, visual_style: str) -> str:
    char_lookup = {c["character_id"]: c for c in characters}

    setting = clip.get("setting", scene.get("setting", ""))
    character_actions = clip.get("character_actions", scene.get("character_actions", ""))
    camera = clip.get("camera") or scene.get("camera", {})
    camera_block = (
        f"{camera.get('angle', '')}. {camera.get('movement', '')}. {camera.get('lens_effect', '')}."
    )
    dialogue_block = build_dialogue_block({"audio": {"dialogue": clip.get("dialogue", [])}}, char_lookup)

    return f"""Visual style: {visual_style}

Characters: {build_character_block(characters)}

Setting: {setting}

Character actions: {character_actions}

Camera: {camera_block}

Dialogue: {dialogue_block}"""


def _save_prompt_sidecar(image_path: str, prompt: str) -> str:
    sidecar_path = str(Path(image_path).with_name(Path(image_path).stem + "_prompt.txt"))
    with open(sidecar_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    return sidecar_path


def _generate_frame_image(
    client, system_prompt: str, user_prompt: str, reference_image_paths: list, output_path: str
) -> str:
    contents = [user_prompt, *_load_image_parts(reference_image_paths)]
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_modalities=["IMAGE"],
        ),
    )

    if (
        not response.candidates
        or not response.candidates[0].content
        or not response.candidates[0].content.parts
    ):
        raise RuntimeError(f"Gemini returned no image content for {output_path}")

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image = PILImage.open(BytesIO(part.inline_data.data))
            image.save(output_path)
            return str(output_path)

    raise RuntimeError(f"Gemini response had no inline image data for {output_path}")


def generate_clip_frame_images(
    client,
    scenario: dict,
    scene_id: int,
    output_dir: str,
    reference_image_paths: list = None,
) -> list:
    """
    Generates a first-frame and last-frame image for every clip in the given
    scene. Clip 1 gets a freshly generated first frame; every later clip's
    first frame reuses the previous clip's generated last frame (image
    chaining) instead of generating a new one, for continuity.

    Returns a list of {clip_id, first_frame_path, last_frame_path}, in clip order.
    """
    scene = next((s for s in scenario["scenes"] if s["scene_id"] == scene_id), None)
    if scene is None:
        raise ValueError(f"No scene found with id {scene_id}")

    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    ref_paths = reference_image_paths or REFERENCE_IMAGE_PATHS

    images_dir = Path(output_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    frame_pairs = []
    prev_last_frame_path = None

    for clip in scene["clips"]:
        clip_id = clip["clip_id"]
        context_text = _clip_context_text(scene, clip, characters, visual_style)

        if prev_last_frame_path is None:
            first_frame_path = str(images_dir / f"scene{scene_id}_clip{clip_id}_first.png")
            print(f"  Writing visual prompt: scene {scene_id} clip {clip_id} first frame...")
            first_frame_prompt = _write_frame_visual_prompt(client, context_text, is_first_frame=True)
            _save_prompt_sidecar(first_frame_path, first_frame_prompt)
            print(f"  Generating first frame: scene {scene_id} clip {clip_id}...")
            _generate_frame_image(
                client,
                FIRST_FRAME_SYSTEM_PROMPT,
                first_frame_prompt,
                ref_paths,
                first_frame_path,
            )
        else:
            first_frame_path = prev_last_frame_path
            print(
                f"  Reusing previous clip's last frame as scene {scene_id} clip {clip_id}'s first frame."
            )

        last_frame_path = str(images_dir / f"scene{scene_id}_clip{clip_id}_last.png")
        print(f"  Writing visual prompt: scene {scene_id} clip {clip_id} last frame...")
        last_frame_prompt = _write_frame_visual_prompt(client, context_text, is_first_frame=False)
        _save_prompt_sidecar(last_frame_path, last_frame_prompt)
        print(f"  Generating last frame: scene {scene_id} clip {clip_id}...")
        _generate_frame_image(
            client,
            LAST_FRAME_SYSTEM_PROMPT,
            last_frame_prompt,
            [*ref_paths, first_frame_path],
            last_frame_path,
        )

        frame_pairs.append(
            {
                "clip_id": clip_id,
                "first_frame_path": first_frame_path,
                "last_frame_path": last_frame_path,
            }
        )
        prev_last_frame_path = last_frame_path

    return frame_pairs
