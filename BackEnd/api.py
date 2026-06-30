from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from Script_Generation_Pipeline.Preprocessing.html_crawler import crawl
import Script_Generation_Pipeline.Script_With_Dpoints.anthropic_script_generation as anthropic_script_generation
import Script_Generation_Pipeline.Script_With_Dpoints.gemini_script_generation as gemini_script_generation

from pydantic import BaseModel
from pathlib import Path
import os
import re
import tempfile
from typing import Any
import json

class SceneInformation(BaseModel):
    book_title: str
    unit_num: int
    chapter_num: int | None = None
    page_num: str | None = None
    user_query: str
    model_choice: str
    video_type: str = "scenario"

class ModifiedScript(BaseModel):
    script: dict[str, Any]


api_router = APIRouter()

# This endpoint will be called by the frontend to generate the initial script based on the user's query and the relevant textbook content (currently with decision points included)
@api_router.post("/initial_script")
def generate_initial_script(scene_information: SceneInformation, background_tasks: BackgroundTasks) -> dict:
    ## parser functionality call
    parsedResult = crawl(
        scene_information.book_title,
        unit_num=scene_information.unit_num,
        chapter_num=scene_information.chapter_num, 
        page_num=scene_information.page_num,
    )

    # Merge all pages into one Markdown file
    merged = "\n\n---\n\n".join(p["markdown"] for p in parsedResult["pages"])

    # Build a more descriptive name
    def _slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
 
    parts = [_slugify(scene_information.book_title)]
    if scene_information.unit_num is not None: parts.append(f"unit-{scene_information.unit_num}")
    if scene_information.chapter_num is not None: parts.append(f"ch-{scene_information.chapter_num}")
    if scene_information.page_num is not None: parts.append(f"p-{scene_information.page_num}")
 
    # Write the merged textbook markdown to a writable directory. On Vercel (and
    # other serverless hosts) the deployment filesystem is read-only except for
    # the system temp dir, so default there; allow an override via env var.
    output_dir = Path(
        os.getenv("TEXTBOOK_CONTEXT_DIR")
        or (Path(tempfile.gettempdir()) / "Textbook_Context")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / f"{'_'.join(parts)}.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)

    # script generation functionality call
    initial_script = None

    if scene_information.model_choice == "anthropic":
        initial_script, file_ids = anthropic_script_generation.generate_script_with_decision_points(str(md_path), scene_information.user_query)

        for file_id in file_ids:
            background_tasks.add_task(anthropic_script_generation.delete_uploaded_file, file_id)

    elif scene_information.model_choice == "gemini":
        initial_script, file_ids = gemini_script_generation.generate_script_with_decision_points(str(md_path), scene_information.user_query)

        for file_name in file_ids:
            background_tasks.add_task(gemini_script_generation.delete_uploaded_file, file_name)

    background_tasks.add_task(delete_md_file, md_path)
    
    return {"message": "Initial script generation completed", "script": initial_script}

# This endpoint will be called by the frontend once the user has finished modifying the initial script and is ready to generate the image frames
@api_router.post("/modified_script")
def generate_final_script(modified_script: ModifiedScript) -> dict:
    print("Received modified script:", modified_script.script)
    return {"message": "Final script generation request received"}


@api_router.get("/dummy_paths")
def get_dummy_paths(target: str):
    BACKEND_DIR = Path(__file__).parent

    match target:
        case "script":
            return {
                "script_path": str(
                    BACKEND_DIR / "Video_Generation_Pipeline" / "scenario.json"
                )
            }
        case "images":
            return {
                "image_paths": {
                    "character_images": [
                        {
                            "character_id": "patient_carl",
                            "image_path": str(
                                BACKEND_DIR
                                / "Video_Generation_Pipeline"
                                / "reference_images"
                                / "patient_Carl_reference_image.png"
                            ),
                        },
                        {
                            "character_id": "nurse_maya",
                            "image_path": str(
                                BACKEND_DIR
                                / "Video_Generation_Pipeline"
                                / "reference_images"
                                / "Nurse_Maya_reference_image.png"
                            ),
                        },
                    ],
                    "background_image": {
                        "image_path": str(
                            BACKEND_DIR
                            / "Video_Generation_Pipeline"
                            / "reference_images"
                            / "background_reference_image.png"
                        )
                    },
                }
            }
        case "video":
            return {"video_paths": {
                "video_paths": [{"scene_id": "1", "video_path": str(BACKEND_DIR / "Video_Generation_Pipeline" / "output" / "demo" / "demo_scene_1.mp4")},
                                {"scene_id": "2", "video_path": str(BACKEND_DIR / "Video_Generation_Pipeline" / "output" / "demo" / "demo_scene_2.mp4")}],
                "manim_path": "",
            }}


@api_router.get("/script/{script_path:path}")
def get_script(script_path: str):
    with open(script_path, "r") as f:
        script = json.load(f)
    return {"script": script}

# This endpoint will be called by the frontend to retrieve the generated images to display them in the frontend
@api_router.get("/image/{image_path:path}")
def get_image(image_path: str):
    return FileResponse(image_path, media_type="image/png")


# This endpoint will be called by the frontend to retrieve the generated video to display them in the frontend
@api_router.get("/video/{video_path:path}")
def get_video(video_path: str):
    return FileResponse(video_path, media_type="video/mp4")


def delete_md_file(file_path: Path):
    file_path.unlink()
    print(f"Successfully deleted {file_path}")
