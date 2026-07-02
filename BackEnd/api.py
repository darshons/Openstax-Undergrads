from fastapi import APIRouter, BackgroundTasks, HTTPException
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
import tempfile


# This Class defines the structure of the request body for generating the initial script based on the user's query and the relevant textbook content
class SceneInformation(BaseModel):
    book_title: str
    unit_num: int
    chapter_num: int | None = None
    page_num: str | None = None
    user_query: str
    model_choice: str
    video_type: str


# This Class defines the structure of the request body for generating images
class ImageGenerationRequest(BaseModel):
    script: dict[str, Any]
    background_image_path: str | None = None
    # This field is optional and will be used when generating opening frames
    character_image_file_mapping: dict[str, str] | None = None
    # This field is optional and will be used when generating opening frames
    request_id: str


# This Class defines the structure of the request body for retrying image generation
class ImageRetryRequest(BaseModel):
    image_request: ImageGenerationRequest
    user_feedback: str | None = (
        None  # This field is optional and will be used when retrying image generation based on user feedback
    )
    image_id: str | None = (
        None  # This field is optional and will be used when retrying character image generation or opening frame generation
    )


# Function to delete local files after processing to clean up the server storage
def delete_local_files(file_paths):
    for file_path in file_paths:
        os.remove(file_path)
        print(f"Successfully deleted {file_path}")


# Function to generate a unique identifier (UUID) associated with each request to ensure that files are uniquely named and avoid conflicts
def generate_uuid():
    return str(uuid.uuid4())


# API router instance to define the endpoints for the FastAPI application
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

    # Write the merged textbook markdown to a writable directory.
    # On Vercel (and other serverless hosts) the deployment filesystem is read-only except for the system temp dir, so default there
    output_dir = Path(tempfile.gettempdir()) / "Textbook_Context"
    output_dir.mkdir(parents=True, exist_ok=True)

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

    if initial_script is None or len(initial_script) == 0:
        raise HTTPException(
            status_code=500,
            detail="Initial script generation failed. No script was returned.",
        )

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

    if background_image_file_path is None:
        raise HTTPException(
            status_code=500,
            detail="Background image generation failed. No image was returned.",
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
) -> dict:

    (
        character_image_file_mapping,
        character_uploaded_file_names,
        character_json_file_paths,
    ) = generate_character_images_impl(request.script, request.request_id)

    local_file_paths_to_delete = character_json_file_paths

    background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

    uploaded_file_names_to_delete = character_uploaded_file_names

    background_tasks.add_task(
        gemini_script_generation.delete_uploaded_files, uploaded_file_names_to_delete
    )

    if character_image_file_mapping is None or len(character_image_file_mapping) == 0:
        raise HTTPException(
            status_code=500,
            detail="Character image generation failed. No images were returned.",
        )

    return {
        "message": "Reference image generation completed",
        "character_image_file_mapping": character_image_file_mapping,
    }


# This function is a helper function that encapsulates the logic for generating character images. It is called by the /generate_character_images endpoint and can also be used for retrying character image generation.
def generate_character_images_impl(
    script: dict[str, Any], request_id: str, character_id: str | None = None
) -> tuple[dict[str, str], list[str | None], list[str]]:

    (
        character_image_file_mapping,
        character_uploaded_file_names,
        character_json_file_paths,
    ) = gemini_character_generation.generate_characters(
        script, request_id, character_id
    )

    return (
        character_image_file_mapping,
        character_uploaded_file_names,
        character_json_file_paths,
    )


# This endpoint will be called by the frontend to generate the opening frames based on the script, reference background image, and reference character images
@api_router.post("/generate_opening_frames")
def generate_opening_frames(
    request: ImageGenerationRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    if (
        request.background_image_path is None
        or request.character_image_file_mapping is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Opening frame generation requires both background_image_path and character_image_file_mapping",
        )

    opening_scene_frame_file_mapping, uploaded_file_names, scene_json_file_paths = (
        generate_opening_frames_impl(
            request.script,
            request.background_image_path,
            request.character_image_file_mapping,
            request.request_id,
        )
    )

    background_tasks.add_task(delete_local_files, scene_json_file_paths)

    background_tasks.add_task(
        gemini_script_generation.delete_uploaded_files, uploaded_file_names
    )

    if (
        opening_scene_frame_file_mapping is None
        or len(opening_scene_frame_file_mapping) == 0
    ):
        raise HTTPException(
            status_code=500,
            detail="Opening frame generation failed. No images were returned.",
        )

    return {
        "message": "Opening frame generation completed",
        "opening_scene_frame_file_mapping": opening_scene_frame_file_mapping,
    }


# This function is a helper function that encapsulates the logic for generating opening frames. It is called by the /generate_opening_frames endpoint and can also be used for retrying opening frame generation.
def generate_opening_frames_impl(
    script: dict[str, Any],
    background_image_path: str,
    character_image_file_mapping: dict[str, str],
    request_id: str,
    scene_id: str | None = None,
) -> tuple[dict[str, str], list[str | None], list[str]]:
    opening_scene_frame_file_mapping, uploaded_file_names, scene_json_file_paths = (
        gemini_frame_generation.generate_frames(
            script,
            background_image_path,
            character_image_file_mapping,
            request_id,
            scene_id=scene_id,
        )
    )

    return opening_scene_frame_file_mapping, uploaded_file_names, scene_json_file_paths


# This endpoint will be called by the frontend to retrieve the generated images to display them in the frontend
@api_router.get("/image/{image_path:path}")
def get_image(image_path: str):
    return FileResponse(image_path, media_type="image/png")


# This endpoint will be called by the frontend to retry background image generation based on user feedback or to simply regenerate the background image if no feedback is provided
@api_router.post("/retry_generate_background_image")
def retry_generate_background_image(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:
        return generate_background_image(
            image_retry_request.image_request, background_tasks
        )
    else:
        return (
            {}
        )  # Implement logic to handle user feedback and retry background image generation


# This endpoint will be called by the frontend to retry character image generation based on user feedback or to simply regenerate the character image if no feedback is provided
@api_router.post("/retry_generate_character_image")
def retry_generate_character_image(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:
        (
            character_image_file_mapping,
            character_uploaded_file_names,
            character_json_file_paths,
        ) = generate_character_images_impl(
            image_retry_request.image_request.script,
            image_retry_request.image_request.request_id,
            character_id=image_retry_request.image_id,
        )

        local_file_paths_to_delete = character_json_file_paths

        background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

        uploaded_file_names_to_delete = character_uploaded_file_names

        background_tasks.add_task(
            gemini_script_generation.delete_uploaded_files,
            uploaded_file_names_to_delete,
        )

        if (
            character_image_file_mapping is None
            or len(character_image_file_mapping) == 0
        ):
            raise HTTPException(
                status_code=500,
                detail="Character image generation failed. No images were returned.",
            )

        return {
            "message": "Reference image generation completed",
            "character_image_file_mapping": character_image_file_mapping,
        }

    else:
        return (
            {}
        )  # Implement logic to handle user feedback and retry character image generation


# This endpoint will be called by the frontend to retry opening frame generation based on user feedback or to simply regenerate the opening frames if no feedback is provided
@api_router.post("/retry_generate_opening_frames")
def retry_generate_opening_frames(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:

        if (
            image_retry_request.image_request.background_image_path is None
            or image_retry_request.image_request.character_image_file_mapping is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Opening frame generation requires both background_image_path and character_image_file_mapping",
            )

        (
            opening_scene_frame_file_mapping,
            uploaded_file_names,
            scene_json_file_paths,
        ) = generate_opening_frames_impl(
            image_retry_request.image_request.script,
            image_retry_request.image_request.background_image_path,
            image_retry_request.image_request.character_image_file_mapping,
            image_retry_request.image_request.request_id,
            scene_id=image_retry_request.image_id,
        )

        local_file_paths_to_delete = scene_json_file_paths

        background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

        uploaded_file_names_to_delete = uploaded_file_names

        background_tasks.add_task(
            gemini_script_generation.delete_uploaded_files,
            uploaded_file_names_to_delete,
        )

        if (
            opening_scene_frame_file_mapping is None
            or len(opening_scene_frame_file_mapping) == 0
        ):
            raise HTTPException(
                status_code=500,
                detail="Opening frame generation failed. No image was returned.",
            )

        return {
            "message": "Opening frame generation retry completed",
            "opening_scene_frame_file_mapping": opening_scene_frame_file_mapping,
        }
    else:
        return (
            {}
        )  # Implement logic to handle user feedback and retry opening frame generation


# This endpoint will be called by the frontend to retrieve the generated video to display them in the frontend
@api_router.get("/video/{video_path:path}")
def get_video(video_path: str):
    return FileResponse(video_path, media_type="video/mp4")
