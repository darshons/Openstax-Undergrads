from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from Script_Generation_Pipeline import crawl
from Script_Generation_Pipeline import (
    generate_script_with_decision_points_anthropic,
    delete_uploaded_files_anthropic,
    generate_script_with_decision_points_gemini,
    delete_uploaded_files_gemini,
    setup_gemini_client,
)
from Image_Generation_Pipeline import (
    generate_background,
    retry_with_feedback,
)
from Video_Generation_Pipeline.video_generator.clip_planner import (
    plan_scenario_clips,
    ClipPlanningError,
)
from Video_Generation_Pipeline.video_generator.pipeline import run_scenario_pipeline

from API.instructor_api_helpers import (
    generate_uuid,
    delete_local_files,
    generate_character_images_impl,
    generate_opening_frame_images_impl,
    setup_supabase_client,
)

from pydantic import BaseModel
from pathlib import Path
import os
import re
from typing import Any
import tempfile
import json
import traceback
from concurrent.futures import ThreadPoolExecutor

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


# This endpoint will be called by the frontend to retrieve the generated images to display them in the frontend
@instructor_router.get("/image/{image_path:path}")
def get_image(image_path: str):
    return FileResponse(image_path, media_type="image/png")


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
                detail="Character image generation failed. No image was returned.",
            )

        return {
            "message": "Opening frame generation retry completed",
            "opening_frame_image_file_path": updated_image_path,
        }


# This endpoint will be called by the frontend to retrieve the generated video to display them in the frontend
@instructor_router.get("/video/{video_path:path}")
def get_video(video_path: str):
    return FileResponse(video_path, media_type="video/mp4")


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
# Scenario video generation (Veo)
# ---------------------------------------------------------------------------

# Anchor the output root at the repo root so it is the same directory whether
# the API or the CLI (video_generator/cli.py) writes/reads it.
_VIDEO_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_OUTPUT_ROOT = os.environ.get(
    "VIDEO_OUTPUT_ROOT",
    os.path.join(_VIDEO_REPO_ROOT, "Video_Generation_Pipeline", "output", "video_runs"),
)
# One worker: Veo extension clips within a scene must be generated serially,
# and this also means one scenario's videos are generated at a time.
_video_executor = ThreadPoolExecutor(max_workers=1)


# This Class defines the structure of the request body for generating scenario videos. background_image_path and character_image_file_mapping come straight from the asset-generation step and are used as Veo reference images for character/environment consistency.
class VideoGenerationRequest(BaseModel):
    script: dict[str, Any]
    request_id: str
    background_image_path: str
    character_image_file_mapping: dict[str, str]


def _video_status_path(request_id: str) -> str:
    return os.path.join(VIDEO_OUTPUT_ROOT, request_id, "status.json")


def _write_video_status(request_id: str, status: dict) -> None:
    """Write status.json atomically — write to a sibling temp file then
    os.replace() over the real path, so a concurrent /video_status read can
    never observe a truncated/partial write mid-json.dump (reproduced during
    real testing: a poll landing mid-write raised JSONDecodeError)."""
    path = _video_status_path(request_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    os.replace(tmp_path, path)


def _run_video_generation(
    script: dict, request_id: str, reference_images: list[str]
) -> None:
    """Background job: plan clips for every scene, then render each scene
    through Veo. Writes status.json after every stage/scene transition so
    /video_status can report progress without blocking on the whole run.
    Any unexpected failure still leaves status.json in a terminal "failed"
    state rather than letting the background thread die silently."""
    status = {"state": "planning_clips", "completed_scenes": {}, "failed_scenes": {}}
    _write_video_status(request_id, status)

    try:
        client = setup_gemini_client()

        try:
            planned_scenario = plan_scenario_clips(script, client=client)
        except ClipPlanningError as e:
            status["state"] = "failed"
            status["error"] = f"clip planning failed: {e}"
            _write_video_status(request_id, status)
            return

        status["state"] = "rendering"
        _write_video_status(request_id, status)

        def _on_scene_complete(result: dict) -> None:
            scene_id = str(result["scene_id"])
            if result["success"]:
                status["completed_scenes"][scene_id] = result["output_file"]
            else:
                status["failed_scenes"][scene_id] = result["error"]
            _write_video_status(request_id, status)

        run_scenario_pipeline(
            client=client,
            scenario=planned_scenario,
            reference_images=reference_images or None,
            on_scene_complete=_on_scene_complete,
        )

        status["state"] = (
            "done" if not status["failed_scenes"] else "completed_with_errors"
        )
        _write_video_status(request_id, status)
    except Exception as e:
        status["state"] = "failed"
        status["error"] = str(e)
        _write_video_status(request_id, status)
        print(
            f"[generate_videos] request {request_id} failed:\n{traceback.format_exc()}"
        )


# This endpoint will be called by the frontend to kick off scenario video generation once assets are approved
@instructor_router.post("/generate_videos")
def generate_videos(request: VideoGenerationRequest) -> dict:
    """Kick off Veo scenario video generation for an approved scenario script.
    Returns immediately; poll /video_status/{request_id} for progress."""
    reference_images = [
        request.background_image_path,
        *request.character_image_file_mapping.values(),
    ]
    _video_executor.submit(
        _run_video_generation, request.script, request.request_id, reference_images
    )
    return {"status": "started", "request_id": request.request_id}


# This endpoint will be called by the frontend to poll scenario video generation progress
@instructor_router.get("/video_status/{request_id}")
def video_status(request_id: str) -> dict:
    """Read the background job's status.json for a run (pure file read; the
    job rewrites it after every stage/scene transition)."""
    status_path = _video_status_path(request_id)
    if not os.path.exists(status_path):
        return {"state": "queued", "completed_scenes": {}, "failed_scenes": {}}
    with open(status_path, "r", encoding="utf-8") as f:
        return json.load(f)
