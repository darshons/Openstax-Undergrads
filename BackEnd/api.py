from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from Script_Generation_Pipeline.Preprocessing.html_crawler import crawl
import Script_Generation_Pipeline.Script_With_Dpoints.anthropic_script_generation as anthropic_script_generation
import Script_Generation_Pipeline.Script_With_Dpoints.gemini_script_generation as gemini_script_generation
import Image_Generation_Pipeline.Background_Generation.gemini_background_generate as gemini_background_generation
import Image_Generation_Pipeline.Character_Generation.gemini_character_generate as gemini_character_generation
import Image_Generation_Pipeline.Frame_Generation.gemini_frame_generate as gemini_frame_generation

from pydantic import BaseModel
from pathlib import Path
import re
from typing import Any
import os
import uuid


# This Class defines the structure of the request body for generating the initial script based on the user's query and the relevant textbook content
class SceneInformation(BaseModel):
    book_title: str
    unit_num: int
    chapter_num: int | None
    page_num: str | None
    user_query: str
    model_choice: str


# This Class defines the structure of the request body for generating images
class ImageGenerationRequest(BaseModel):
    script: dict[str, Any]
    background_image_path: (
        str | None
    )  # This field is optional and will be used when generating opening frames
    character_image_file_mapping: (
        dict[str, str] | None
    )  # This field is optional and will be used when generating opening frames
    request_id: str


# This Class defines the structure of the request body for retrying image generation
class ImageRetryRequest(BaseModel):
    image_request: ImageGenerationRequest
    user_feedback: (
        str | None
    )  # This field is optional and will be used when retrying image generation based on user feedback
    image_id: (
        str | None
    )  # This field is optional and will be used when retrying character image generation or opening frame generation


# Function to delete local files after processing to clean up the server storage
def delete_local_files(file_paths):
    for file_path in file_paths:
        os.remove(file_path)
        print(f"Successfully deleted {file_path}")


# Function to generate a unique identifier (UUID) associated with each request to ensure that files are uniquely named and avoid conflicts
def generate_uuid():
    return str(uuid.uuid4())


api_router = APIRouter()


# This endpoint will be called by the frontend to generate the initial script based on the user's query and the relevant textbook content (currently with decision points included)
@api_router.post("/initial_script")
def generate_initial_script(
    scene_information: SceneInformation, background_tasks: BackgroundTasks
) -> dict:
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
    if scene_information.unit_num is not None:
        parts.append(f"unit-{scene_information.unit_num}")
    if scene_information.chapter_num is not None:
        parts.append(f"ch-{scene_information.chapter_num}")
    if scene_information.page_num is not None:
        parts.append(f"p-{scene_information.page_num}")

    # Make absolute position in the project folder
    PROJECT_DIR = Path(__file__).resolve().parent
    output_dir = PROJECT_DIR / "Script_Generation_Pipeline" / "Textbook_Context"

    md_path = output_dir / f"{'_'.join(parts)}.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)

    # script generation functionality call
    initial_script = None

    if scene_information.model_choice == "anthropic":
        initial_script, file_ids = (
            anthropic_script_generation.generate_script_with_decision_points(
                str(md_path), scene_information.user_query
            )
        )

        background_tasks.add_task(
            anthropic_script_generation.delete_uploaded_files, file_ids
        )

    elif scene_information.model_choice == "gemini":
        initial_script, file_ids = (
            gemini_script_generation.generate_script_with_decision_points(
                str(md_path), scene_information.user_query
            )
        )

        background_tasks.add_task(
            gemini_script_generation.delete_uploaded_files, file_ids
        )

    background_tasks.add_task(
        delete_local_files, [md_path]
    )  # delete the merged markdown file after processing

    uuid = generate_uuid()

    return {
        "message": "Initial script generation completed",
        "script": initial_script,
        "request_id": uuid,
    }


# This endpoint will be called by the frontend to generate the reference background image
@api_router.post("/generate_background_image")
def generate_background_image(
    request: ImageGenerationRequest, background_tasks: BackgroundTasks
) -> dict:

    (
        background_image_file_path,
        background_uploaded_file_names,
        background_json_file_path,
    ) = gemini_background_generation.generate_background(
        request.script, request.request_id
    )

    local_file_paths_to_delete = background_json_file_path

    background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

    uploaded_file_names_to_delete = background_uploaded_file_names

    background_tasks.add_task(
        gemini_script_generation.delete_uploaded_files, uploaded_file_names_to_delete
    )

    return {
        "message": "Reference image generation completed",
        "background_image_file_path": background_image_file_path,
    }


# This endpoint will be called by the frontend to generate the reference character images
@api_router.post("/generate_character_images")
def generate_character_images(
    request: ImageGenerationRequest,
    background_tasks: BackgroundTasks,
    character_id: str | None = None,
) -> dict:

    (
        character_image_file_mapping,
        character_uploaded_file_names,
        character_json_file_paths,
    ) = gemini_character_generation.generate_characters(
        request.script, request.request_id, character_id
    )

    local_file_paths_to_delete = character_json_file_paths

    background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

    uploaded_file_names_to_delete = character_uploaded_file_names

    background_tasks.add_task(
        gemini_script_generation.delete_uploaded_files, uploaded_file_names_to_delete
    )

    return {
        "message": "Reference image generation completed",
        "character_image_file_mapping": character_image_file_mapping,
    }


# This endpoint will be called by the frontend to generate the opening frames based on the script, reference background image, and reference character images
@api_router.post("/generate_opening_frames")
def generate_opening_frames(
    request: ImageGenerationRequest,
    background_tasks: BackgroundTasks,
    scene_id: str | None = None,
) -> dict:

    opening_scene_frame_file_mapping, uploaded_file_names, scene_json_file_paths = (
        gemini_frame_generation.generate_frames(
            request.script,
            request.background_image_path,
            request.character_image_file_mapping,
            request.request_id,
            scene_id=scene_id,
        )
    )

    background_tasks.add_task(delete_local_files, scene_json_file_paths)

    background_tasks.add_task(
        gemini_script_generation.delete_uploaded_files, uploaded_file_names
    )

    return {
        "message": "Opening frame generation completed",
        "opening_scene_frame_file_mapping": opening_scene_frame_file_mapping,
    }


# This endpoint will be called by the frontend to retrieve the generated images to display them in the frontend
@api_router.get("/image/{image_path:path}")
def get_image(image_path: str):
    return FileResponse(image_path, media_type="image/png")


@api_router.post("/retry_generate_background_image")
def retry_generate_background_image(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:
        return generate_background_image(
            image_retry_request.image_request, background_tasks
        )
    else:
        return {}  # Implement logic to handle user feedback and retry background image generation


@api_router.post("/retry_generate_character_image")
def retry_generate_character_image(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:
        return generate_character_images(
            image_retry_request.image_request,
            background_tasks,
            character_id=image_retry_request.image_id,
        )
    else:
        return {}  # Implement logic to handle user feedback and retry character image generation


@api_router.post("/retry_generate_opening_frames")
def retry_generate_opening_frames(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:
        return generate_opening_frames(
            image_retry_request.image_request,
            background_tasks,
            scene_id=image_retry_request.image_id,
        )
    else:
        return {}  # Implement logic to handle user feedback and retry opening frame generation
    
