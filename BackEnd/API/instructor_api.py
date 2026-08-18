from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from Script_Generation_Pipeline import (
    generate_script_with_decision_points_anthropic,
    delete_uploaded_files_anthropic,
    generate_script_with_decision_points_gemini,
    delete_uploaded_files_gemini,
    generate_script_with_decision_points_local,
    crawl,
)

from Script_Generation_Pipeline.render_mode import normalize_render_modes

from Image_Generation_Pipeline import (
    generate_background,
    generate_opening_frames,
    retry_with_feedback,
)

from API.instructor_api_helpers import (
    generate_uuid,
    delete_local_files,
    generate_character_images_impl,
    setup_supabase_client,
    video_status_path,
    run_video_generation,
    file_path_guard,
    get_image_roots,
    get_video_roots,
)

from Video_Generation_Pipeline.manim_generator.pipeline import (
    read_run_context,
    regenerate_scene,
    run_scenario_pipeline,
)
from Video_Generation_Pipeline.manim_generator.assets_index import (
    list_run_assets,
    media_type_for,
    resolve_asset_path,
)
from Video_Generation_Pipeline.manim_generator.script_adapter import (
    ScriptValidationError,
    adapt,
)

from pydantic import BaseModel
from pathlib import Path
import logging
import re
from typing import Any
import tempfile
import json
import os
import json
from storage3.exceptions import StorageApiError


# This Class defines the structure of the request body for generating the initial script based on the user's query and the relevant textbook content
class SceneInformation(BaseModel):
    book_title: str
    unit_num: int
    chapter_num: int | None = None
    page_num: str | None = None
    user_query: str
    model_choice: str | None = None
    video_type: str


# This Class defines the structure of the request body for generating images
class VisualGenerationRequest(BaseModel):
    script: dict[str, Any]
    background_image_path: str | None = (
        None  # This field is optional and will be used when generating opening frames
    )
    character_image_file_mapping: dict[str, str] | None = (
        None  # This field is optional and will be used when generating opening frames
    )
    request_id: str


# This Class defines the structure of the request body for retrying image generation
class ImageRetryRequest(BaseModel):
    image_request: VisualGenerationRequest
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


# TODO: Review
# This endpoint will be called by the frontend to generate the initial script based on the user's query and the relevant textbook content (currently with decision points included)
@instructor_router.post("/initial_script")
def generate_initial_script(
    scene_information: SceneInformation, background_tasks: BackgroundTasks
) -> dict:
    ## parser functionality call
    try:
        parsedResult = crawl(
            scene_information.book_title,
            unit_num=scene_information.unit_num,
            chapter_num=scene_information.chapter_num,
            page_num=scene_information.page_num,
        )
    except ValueError as e:
        # The crawler raises ValueError for unknown book/unit/chapter/page and the
        # message lists what is actually available — surface it to the caller
        # instead of letting it become an opaque 500.
        raise HTTPException(status_code=404, detail=str(e))

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

    model_choice = scene_information.model_choice

    if model_choice == "anthropic":
        initial_script, file_ids = generate_script_with_decision_points_anthropic(
            str(md_path), scene_information.user_query
        )

        background_tasks.add_task(delete_uploaded_files_anthropic, file_ids)

    elif model_choice == "gemini":
        initial_script, file_ids = generate_script_with_decision_points_gemini(
            str(md_path), scene_information.user_query
        )

        background_tasks.add_task(delete_uploaded_files_gemini, file_ids)

    elif model_choice == "local":
        # Shells out to the Claude Code CLI; nothing is uploaded, no cleanup task
        initial_script, _ = generate_script_with_decision_points_local(
            str(md_path), scene_information.user_query
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model_choice '{model_choice}'. "
            "Valid options: 'anthropic', 'gemini', 'local'.",
        )

    background_tasks.add_task(
        delete_local_files, [md_path]
    )  # delete the merged markdown file after processing

    request_id = generate_uuid()

    if initial_script is None or len(initial_script) == 0:
        raise HTTPException(
            status_code=500,
            detail="Initial script generation failed. No script was returned.",
        )

    normalize_render_modes(initial_script, scene_information.video_type)

    return {
        "message": "Initial script generation completed",
        "script": initial_script,
        "request_id": request_id,
    }


# This endpoint will be called by the frontend to generate the reference background image
@instructor_router.post("/generate_background_image")
def generate_background_image(
    request: VisualGenerationRequest, background_tasks: BackgroundTasks
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
    request: VisualGenerationRequest,
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


# This endpoint will be called by the frontend to composite opening-frame images per scene from the background + character references
@instructor_router.post("/generate_opening_frames")
def generate_opening_frames_endpoint(
    request: VisualGenerationRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    if not request.background_image_path or not request.character_image_file_mapping:
        raise HTTPException(
            status_code=400,
            detail="Opening frame generation requires both background_image_path and character_image_file_mapping",
        )

    (
        opening_scene_frame_file_mapping,
        frame_uploaded_file_names,
        frame_json_file_paths,
    ) = generate_opening_frames(
        request.script,
        request.background_image_path,
        request.character_image_file_mapping,
        request.request_id,
    )

    background_tasks.add_task(delete_local_files, frame_json_file_paths)
    background_tasks.add_task(delete_uploaded_files_gemini, frame_uploaded_file_names)

    if opening_scene_frame_file_mapping is None or len(opening_scene_frame_file_mapping) == 0:
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
    return FileResponse(
        file_path_guard(image_path, get_image_roots()), media_type="image/png"
    )


# This endpoint will be called by the frontend to retrieve the generated video to display them in the frontend
@instructor_router.get("/video/{video_path:path}")
def get_video(video_path: str):
    return FileResponse(
        file_path_guard(video_path, get_video_roots()), media_type="video/mp4"
    )


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


# This endpoint will be called by the frontend to retry opening-frame generation for one scene based on user feedback, or to simply regenerate it if no feedback is provided
@instructor_router.post("/retry_generate_opening_frames")
def retry_generate_opening_frames(
    image_retry_request: ImageRetryRequest, background_tasks: BackgroundTasks
) -> dict:
    if (
        not image_retry_request.image_request.background_image_path
        or not image_retry_request.image_request.character_image_file_mapping
    ):
        raise HTTPException(
            status_code=400,
            detail="Opening frame retry requires both background_image_path and character_image_file_mapping",
        )

    if image_retry_request.user_feedback is None:
        (
            opening_scene_frame_file_mapping,
            frame_uploaded_file_names,
            frame_json_file_paths,
        ) = generate_opening_frames(
            image_retry_request.image_request.script,
            image_retry_request.image_request.background_image_path,
            image_retry_request.image_request.character_image_file_mapping,
            image_retry_request.image_request.request_id,
            retry_image_id=image_retry_request.retry_image_id,
        )

        background_tasks.add_task(delete_local_files, frame_json_file_paths)
        background_tasks.add_task(
            delete_uploaded_files_gemini, frame_uploaded_file_names
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
                detail="Original opening frame image not found.",
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


# This endpoint will be called by the frontend to poll scenario video generation progress
@instructor_router.get("/video_status/{request_id}")
def video_status(request_id: str) -> dict:
    """Read the background job's status.json for a run (pure file read; the
    job rewrites it after every stage/scene transition)."""

    status_path = video_status_path(request_id)

    if not os.path.exists(status_path):
        return {"state": "queued", "completed_scenes": {}, "failed_scenes": {}}

    with open(status_path, "r", encoding="utf-8") as f:
        return json.load(f)


# This endpoint will be called by the frontend to kick off scenario video generation once assets are approved
@instructor_router.post("/generate_videos")
def generate_videos(
    request: VisualGenerationRequest, background_tasks: BackgroundTasks
) -> dict:
    """Kick off solo-clip-technique video generation for an approved scenario
    script. Returns immediately; poll /video_status/{request_id} for progress."""
    if (
        request.background_image_path is None
        or request.character_image_file_mapping is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Video generation requires both background_image_path and character_image_file_mapping",
        )

    background_tasks.add_task(
        run_video_generation,
        request.script,
        request.request_id,
        request.background_image_path,
        request.character_image_file_mapping,
    )
    return {"status": "started"}


# ---------------------------------------------------------------------------
# Manim branching-video generation ("Manim · Graphics" video type)
# ---------------------------------------------------------------------------
from concurrent.futures import ThreadPoolExecutor

# Anchor the output root at the system temp dir: on Vercel (and other serverless
# hosts) the deployment filesystem is read-only except for the temp dir, so a
# repo-relative "output/" is unwritable there. Using an absolute path also keeps
# the root identical whether the pipeline is launched by the API (cwd=BackEnd/)
# or the CLI (cwd=repo root). Override with MANIM_OUTPUT_ROOT for a durable dir.
MANIM_OUTPUT_ROOT = os.environ.get(
    "MANIM_OUTPUT_ROOT", str(Path(tempfile.gettempdir()) / "Manim_Video_Output")
)
os.makedirs(MANIM_OUTPUT_ROOT, exist_ok=True)
# One worker: scenario renders must be serial (parallel manim subprocesses
# deadlock), and this also means one scenario is generated at a time.
_manim_executor = ThreadPoolExecutor(max_workers=1)


class ManimVideoRequest(BaseModel):
    script: dict[str, Any]
    request_id: str


@instructor_router.post("/generate_manim_videos")
def generate_manim_videos(
    request: ManimVideoRequest, background_tasks: BackgroundTasks
) -> dict:
    """Kick off Manim branching-video generation for an edited scenario script.
    Returns immediately; poll /manim_video_status/{request_id} for progress."""
    try:
        adapt(request.script)  # fail fast on an inconsistent branch graph
    except ScriptValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    background_tasks.add_task(
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
    status_path = os.path.join(_manim_run_dir(request_id), "status.json")
    if not os.path.exists(status_path):
        return {"state": "queued", "completed_scenes": {}, "failed_scenes": {}}
    with open(status_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Manim intermediate assets: inspect, edit, regenerate
#
# The Veo pipeline lets the user review and regenerate each intermediate before
# the final video (script, background, characters, opening frames). These give
# the Manim pipeline the same control surface over what it produces: each
# scene's plan, its generated Manim source, the grid-critic snapshots, and the
# render error logs — plus a way to re-render one scene from edited input.
# ---------------------------------------------------------------------------


def _manim_run_dir(request_id: str) -> str:
    """Resolve a request_id to its run directory, refusing ids that escape the
    output root (the id reaches us straight from the caller)."""
    if not request_id or "/" in request_id or "\\" in request_id or request_id.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid request_id")
    root = os.path.realpath(MANIM_OUTPUT_ROOT)
    run_dir = os.path.realpath(os.path.join(root, request_id))
    if run_dir != root and not run_dir.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid request_id")
    return run_dir


class SceneRegenerateRequest(BaseModel):
    """All three overrides are optional; supplying none re-renders the scene
    from scratch (a plain retry). ``plan`` skips the planner, ``code`` also
    skips codegen so the user's own Manim source is rendered verbatim."""

    plan: str | None = None
    code: str | None = None
    script: dict[str, Any] | None = None
    restitch: bool = True


@instructor_router.get("/manim_assets/{request_id}")
def list_manim_assets(request_id: str):
    """Inventory of everything a run produced, grouped per scene, so the
    frontend can show the intermediates instead of just the final video."""
    run_dir = _manim_run_dir(request_id)
    try:
        assets = list_run_assets(run_dir)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No run found for {request_id}")
    return {"request_id": request_id, **assets}


@instructor_router.get("/manim_asset/{request_id}/{asset_path:path}")
def get_manim_asset(request_id: str, asset_path: str):
    """Serve one intermediate by its run-relative path (as listed by
    /manim_assets). Confined to the run directory."""
    run_dir = _manim_run_dir(request_id)
    try:
        target = resolve_asset_path(run_dir, asset_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No such asset: {asset_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return FileResponse(target, media_type=media_type_for(target))


@instructor_router.post("/regenerate_manim_scene/{request_id}/{scene_id}")
def regenerate_manim_scene(request_id: str, scene_id: int, request: SceneRegenerateRequest):
    """Re-render ONE scene of an existing run from edited input, reusing the
    frozen asset kit so the other scenes and character consistency are
    untouched. Returns immediately; poll /manim_video_status for progress.

    Shares the single Manim worker — parallel manim subprocesses deadlock, so a
    regeneration queues behind any run already in flight."""
    run_dir = _manim_run_dir(request_id)
    if read_run_context(run_dir) is None:
        raise HTTPException(
            status_code=404,
            detail=f"No completed run for {request_id} — a scene can only be "
                   "regenerated after a full run has frozen its asset kit.",
        )

    if request.script is not None:
        try:
            adapt(request.script)  # fail fast on an inconsistent branch graph
        except ScriptValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

    _manim_executor.submit(
        regenerate_scene,
        request_id,
        scene_id,
        MANIM_OUTPUT_ROOT,
        request.plan,
        request.code,
        request.script,
        request.restitch,
    )
    return {"status": "started", "request_id": request_id, "scene_id": scene_id}
