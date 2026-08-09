# Wraps Image_Generation_Pipeline's generate_characters / generate_background
# with a cache check, so producing a scenario's character-portrait and
# background reference images becomes a real pipeline stage - "scenario ->
# reference images -> rig -> clips -> stitch" (see solo_clip/pipeline.py) -
# instead of a step a human has to remember to run first.
#
# Idempotent: if an expected image already exists, it's left alone and the
# underlying (paid) generation call is skipped for that image specifically.
import shutil
import sys
from pathlib import Path

# Image_Generation_Pipeline (and, transitively, Script_Generation_Pipeline,
# which it imports setup_gemini_client from) live under BackEnd/, a sibling
# of Video_Generation_Pipeline - not importable from these scripts' own cwd
# without adding BackEnd/ to sys.path first, same trick used for
# Transcript_Eval_Pipeline elsewhere in this codebase.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _existing_character_image(output_dir: Path, character: dict) -> Path | None:
    """Two naming conventions exist across lessons already: character_id-based
    (nurse_maya.png) and name-based, lowercase (maya.png). Recognize either as
    "already generated" so pre-existing hand-set assets are never silently
    regenerated - only genuinely missing images get created, and new ones are
    always written under the character_id convention."""
    by_id = output_dir / f"{character['character_id']}.png"
    if by_id.exists():
        return by_id
    by_name = output_dir / f"{character['name'].lower()}.png"
    if by_name.exists():
        return by_name
    return None


def ensure_reference_images(scenario: dict, output_dir: Path, request_id: str = "lesson") -> dict:
    """Returns {character_id: path, ..., "background": path}. Generates only
    what's missing from output_dir - safe to call every run."""
    from Image_Generation_Pipeline import generate_background, generate_characters

    output_dir.mkdir(parents=True, exist_ok=True)
    characters = scenario["characters"]

    result = {}
    missing = []
    for character in characters:
        existing = _existing_character_image(output_dir, character)
        if existing:
            result[character["character_id"]] = str(existing)
        else:
            missing.append(character)

    for character in missing:
        cid = character["character_id"]
        print(f"  Generating reference image for {character['name']} ({cid})...")
        image_mapping, _, _ = generate_characters(scenario, request_id, retry_image_id=cid)
        src = image_mapping.get(cid)
        if not src:
            raise RuntimeError(f"ensure_reference_images: generation returned nothing for {cid}")
        dest = output_dir / f"{cid}.png"
        shutil.copy(src, dest)
        result[cid] = str(dest)

    background_path = output_dir / "background_reference_image.png"
    if background_path.exists():
        result["background"] = str(background_path)
    else:
        print("  Generating background reference image...")
        bg_src, _, _ = generate_background(scenario, request_id)
        if not bg_src:
            raise RuntimeError("ensure_reference_images: background generation returned nothing")
        shutil.copy(bg_src, background_path)
        result["background"] = str(background_path)

    return result
