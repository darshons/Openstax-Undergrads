from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from Script_Generation_Pipeline import crawl
from Script_Generation_Pipeline import (
    generate_script_with_decision_points_anthropic,
    delete_uploaded_files_anthropic,
    generate_script_with_decision_points_gemini,
    delete_uploaded_files_gemini,
)
from Image_Generation_Pipeline import (
    generate_background,
    retry_with_feedback,
)

from API.instructor_api_helpers import (
    generate_uuid,
    delete_local_files,
    generate_character_images_impl,
    generate_opening_frame_images_impl,
    setup_supabase_client,
)

import json
from concurrent.futures import ThreadPoolExecutor

from Video_Generation_Pipeline.manim_generator.pipeline import run_scenario_pipeline
from Video_Generation_Pipeline.manim_generator.script_adapter import (
    ScriptValidationError,
    adapt,
)


from pydantic import BaseModel
from pathlib import Path
import re
from typing import Any
import tempfile
import json
import os

from storage3.exceptions import StorageApiError


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


# This Class defines the structure of the request body for generating videos
class VideoGenerationRequest(BaseModel):
    image_request: ImageGenerationRequest
    opening_scene_frame_file_mapping: dict[str, str]


# This Class defines the structure of the request body for retrying image generation
class ImageRetryRequest(BaseModel):
    image_request: ImageGenerationRequest
    user_feedback: str | None = (
        None  # This field is optional and will be used when retrying image generation based on user feedback
    )
    retry_image_id: str | None = (
        None  # This field is optional and will be used when retrying character image generation or opening frame generation
    )


# This Class defines the structure of the request body for uploading project information to the Supabase database
class UploadProjectInfo(BaseModel):
    project_name: str
    script: dict[str, Any]
    video_paths: dict[
        int, str
    ]  # Dictionary containing video paths and their corresponding order


# API router instance to define the endpoints for the FastAPI application for the instructor
instructor_router = APIRouter()


# This endpoint will be called by the frontend to generate the initial script based on the user's query and the relevant textbook content (currently with decision points included)
@instructor_router.post("/initial_script")
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
        initial_script, file_ids = generate_script_with_decision_points_anthropic(
            str(md_path), scene_information.user_query
        )

        background_tasks.add_task(delete_uploaded_files_anthropic, file_ids)

    elif scene_information.model_choice == "gemini":
        initial_script, file_ids = generate_script_with_decision_points_gemini(
            str(md_path), scene_information.user_query
        )

        background_tasks.add_task(delete_uploaded_files_gemini, file_ids)

    background_tasks.add_task(
        delete_local_files, [md_path]
    )  # delete the merged markdown file after processing

    request_id = generate_uuid()

    if initial_script is None or len(initial_script) == 0:
        raise HTTPException(
            status_code=500,
            detail="Initial script generation failed. No script was returned.",
        )

    return {
        "message": "Initial script generation completed",
        "script": initial_script,
        "request_id": request_id,
    }


# This endpoint will be called by the frontend to generate the reference background image
@instructor_router.post("/generate_background_image")
def generate_background_image(
    request: ImageGenerationRequest, background_tasks: BackgroundTasks
) -> dict:

    (
        background_image_file_path,
        background_uploaded_file_names,
        background_json_file_path,
    ) = generate_background(request.script, request.request_id)

    local_file_paths_to_delete = background_json_file_path

    background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

    uploaded_file_names_to_delete = background_uploaded_file_names

    background_tasks.add_task(
        delete_uploaded_files_gemini, uploaded_file_names_to_delete
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
@instructor_router.post("/generate_character_images")
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
        delete_uploaded_files_gemini, uploaded_file_names_to_delete
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


# This endpoint will be called by the frontend to generate the opening frames based on the script, reference background image, and reference character images
@instructor_router.post("/generate_opening_frames")
def generate_opening_frame_images(
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
        generate_opening_frame_images_impl(
            request.script,
            request.background_image_path,
            request.character_image_file_mapping,
            request.request_id,
        )
    )

    background_tasks.add_task(delete_local_files, scene_json_file_paths)

    background_tasks.add_task(delete_uploaded_files_gemini, uploaded_file_names)

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


# This endpoint will be called by the frontend to generate the scene videos based on the script, reference background image, reference character images, and opening frames
@instructor_router.post("/generate_scene_videos")
def generate_scene_videos(
    request: VideoGenerationRequest, background_tasks: BackgroundTasks
) -> dict:
    if (
        request.image_request.background_image_path is None
        or request.image_request.character_image_file_mapping is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Scene video generation requires both background_image_path and character_image_file_mapping",
        )

    # Here you would call your video generation function, passing in the necessary parameters.
    # For example:
    # scene_video_file_mapping, uploaded_file_names, video_local_file_paths = generate_scene_videos(
    #     request.image_request.script,
    #     request.image_request.background_image_path,
    #     request.image_request.character_image_file_mapping,
    #     request.opening_scene_frame_file_mapping,
    #     request.image_request.request_id,
    # )

    scene_video_file_mapping = (
        {}
    )  # Replace with actual mapping from the video generation function (e.g., {scene_id: video_file_path})
    uploaded_file_names = (
        []
    )  # Replace with actual list of uploaded file names (i.e., the names of the video files uploaded to Gemini for each scene if applicable)
    video_local_file_paths = (
        []
    )  # Replace with actual list of JSON file paths (i.e., the paths of the local video files generated for each scene if applicable)

    background_tasks.add_task(delete_local_files, video_local_file_paths)
    background_tasks.add_task(delete_uploaded_files_gemini, uploaded_file_names)

    if scene_video_file_mapping is None or len(scene_video_file_mapping) == 0:
        raise HTTPException(
            status_code=500,
            detail="Scene video generation failed. No videos were returned.",
        )

    return {
        "message": "Scene video generation completed",
        "scene_video_file_mapping": scene_video_file_mapping,
    }


# This endpoint will be called by the frontend to retrieve the generated images to display them in the frontend
@instructor_router.get("/image/{image_path:path}")
def get_image(image_path: str):
    return FileResponse(image_path, media_type="image/png")


# This endpoint will be called by the frontend to retrieve the generated video to display them in the frontend
@instructor_router.get("/video/{video_path:path}")
def get_video(video_path: str):
    return FileResponse(video_path, media_type="video/mp4")


# This endpoint will be called by the frontend to retry background image generation based on user feedback or to simply regenerate the background image if no feedback is provided
@instructor_router.post("/retry_generate_background_image")
def retry_generate_background_image(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if image_retry_request.user_feedback is None:
        return generate_background_image(
            image_retry_request.image_request, background_tasks
        )
    else:
        dir_path = Path(tempfile.gettempdir()) / "Background_Image_Output"
        original_image_path = (
            dir_path
            / f"{image_retry_request.image_request.request_id}_background_reference_image.png"
        )

        if not original_image_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Original background reference image not found.",
            )

        updated_image_path, uploaded_file_names_to_delete = retry_with_feedback(
            str(original_image_path),
            image_retry_request.user_feedback,
        )

        background_tasks.add_task(
            delete_uploaded_files_gemini, uploaded_file_names_to_delete
        )

        if updated_image_path is None:
            raise HTTPException(
                status_code=500,
                detail="Background image generation failed. No image was returned.",
            )

        return {
            "message": "Background image generation retry completed",
            "background_image_file_path": updated_image_path,
        }


# This endpoint will be called by the frontend to retry character image generation based on user feedback or to simply regenerate the character image if no feedback is provided
@instructor_router.post("/retry_generate_character_image")
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
            retry_image_id=image_retry_request.retry_image_id,
        )

        local_file_paths_to_delete = character_json_file_paths

        background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

        uploaded_file_names_to_delete = character_uploaded_file_names

        background_tasks.add_task(
            delete_uploaded_files_gemini,
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
            "message": "Character image generation retry completed",
            "character_image_file_mapping": character_image_file_mapping,
        }

    else:
        dir_path = Path(tempfile.gettempdir()) / "Character_Image_Output"
        original_image_path = (
            dir_path
            / f"{image_retry_request.image_request.request_id}_{image_retry_request.retry_image_id}_reference_image.png"
        )

        if not original_image_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Original character reference image not found.",
            )

        updated_image_path, uploaded_file_names_to_delete = retry_with_feedback(
            str(original_image_path),
            image_retry_request.user_feedback,
        )

        background_tasks.add_task(
            delete_uploaded_files_gemini, uploaded_file_names_to_delete
        )

        if updated_image_path is None:
            raise HTTPException(
                status_code=500,
                detail="Character image generation failed. No image was returned.",
            )

        return {
            "message": "Character image generation retry completed",
            "character_image_file_path": updated_image_path,
        }


# This endpoint will be called by the frontend to retry opening frame generation based on user feedback or to simply regenerate the opening frames if no feedback is provided
@instructor_router.post("/retry_generate_opening_frames")
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
        ) = generate_opening_frame_images_impl(
            image_retry_request.image_request.script,
            image_retry_request.image_request.background_image_path,
            image_retry_request.image_request.character_image_file_mapping,
            image_retry_request.image_request.request_id,
            retry_image_id=image_retry_request.retry_image_id,
        )

        local_file_paths_to_delete = scene_json_file_paths

        background_tasks.add_task(delete_local_files, local_file_paths_to_delete)

        uploaded_file_names_to_delete = uploaded_file_names

        background_tasks.add_task(
            delete_uploaded_files_gemini,
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
        dir_path = Path(tempfile.gettempdir()) / "Frame_Image_Output"
        original_image_path = (
            dir_path
            / f"{image_retry_request.image_request.request_id}_{image_retry_request.retry_image_id}_opening_frame.png"
        )

        if not original_image_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Original opening frame reference image not found.",
            )

        updated_image_path, uploaded_file_names_to_delete = retry_with_feedback(
            str(original_image_path), image_retry_request.user_feedback
        )

        background_tasks.add_task(
            delete_uploaded_files_gemini, uploaded_file_names_to_delete
        )

        if updated_image_path is None:
            raise HTTPException(
                status_code=500,
                detail="Opening frame generation failed. No image was returned.",
            )

        return {
            "message": "Opening frame generation retry completed",
            "opening_frame_image_file_path": updated_image_path,
        }


# This endpoint will be called by the frontend to upload the project information (script and generated videos) to the Supabase database
@instructor_router.post("/upload_project_info")
def upload_project_info(project_info: UploadProjectInfo):
    for video_path in project_info.video_paths.values():
        if not Path(video_path).exists() or not Path(video_path).is_file():
            raise HTTPException(
                status_code=400,
                detail=f"Video file '{video_path}' does not exist.",
            )

    supabase_client = setup_supabase_client()

    try:

        supabase_client.storage.from_("Scripts").upload(
            path=f"{project_info.project_name}/script.json",
            file=json.dumps(project_info.script, indent=2).encode("utf-8"),
            file_options={"content-type": "application/json", "upsert": "false"},
        )

        for order, video_path in project_info.video_paths.items():
            with open(video_path, "rb") as f:
                supabase_client.storage.from_("Videos").upload(
                    path=f"{project_info.project_name}/scene_{order}.mp4",
                    file=f,
                    file_options={
                        "content-type": "video/mp4",
                        "upsert": "false",
                    },
                )

        return {"message": "Project information uploaded successfully"}

    except StorageApiError as e:
        if e.status == 409 or e.code == "Duplicate":
            raise HTTPException(
                status_code=409,
                detail=f"Project with name '{project_info.project_name}' already exists.",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while uploading project information: {str(e)}. Please try again.",
            )


# ---------------------------------------------------------------------------
# Manim branching-video generation ("Manim · Graphics" video type)
# ---------------------------------------------------------------------------

# TODO!: This code does not currently follow the same pattern of saving to a temp directory and cleaning up after itself. It should be refactored to do so, but for now it is left as-is to avoid breaking the existing pipeline.

# Anchor the output root at the repo root so it is the same directory whether
# the pipeline is launched by the API (cwd=BackEnd/) or the CLI (cwd=repo root).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIM_OUTPUT_ROOT = os.environ.get(
    "MANIM_OUTPUT_ROOT", os.path.join(_REPO_ROOT, "output", "manim_runs")
)
# One worker: scenario renders must be serial (parallel manim subprocesses
# deadlock), and this also means one scenario is generated at a time.
_manim_executor = ThreadPoolExecutor(max_workers=1)


class ManimVideoRequest(BaseModel):
    script: dict[str, Any]
    request_id: str


@instructor_router.post("/generate_manim_videos")
def generate_manim_videos(request: ManimVideoRequest):
    """Kick off Manim branching-video generation for an edited scenario script.
    Returns immediately; poll /manim_video_status/{request_id} for progress."""
    try:
        adapt(request.script)  # fail fast on an inconsistent branch graph
    except ScriptValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    _manim_executor.submit(
        run_scenario_pipeline,
        request.script,
        request.request_id,
        MANIM_OUTPUT_ROOT,
    )
    return {"status": "started", "request_id": request.request_id}


@instructor_router.get("/manim_video_status/{request_id}")
def manim_video_status(request_id: str):
    """Read the pipeline's status.json for a run (pure file read; the pipeline
    rewrites it after every stage transition)."""
    status_path = os.path.join(MANIM_OUTPUT_ROOT, request_id, "status.json")
    if not os.path.exists(status_path):
        return {"state": "queued", "completed_scenes": {}, "failed_scenes": {}}
    with open(status_path, "r", encoding="utf-8") as f:
        return json.load(f)
