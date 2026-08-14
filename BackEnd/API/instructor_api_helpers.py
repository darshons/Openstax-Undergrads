import os
import uuid
from typing import Any
import json
import traceback
import tempfile
from supabase import create_client, Client
from pathlib import Path
import logging
from collections.abc import Callable
from fastapi import HTTPException


from Script_Generation_Pipeline import setup_gemini_client

from Image_Generation_Pipeline import (
    generate_characters,
)

from Video_Generation_Pipeline.video_generator.clip_planner import (
    plan_scenario_clips,
    ClipPlanningError,
)

from Video_Generation_Pipeline.solo_clip.pipeline import (
    run_scenario_pipeline_solo_clip,
)

from Video_Generation_Pipeline.video_generator.clip_planner import (
    plan_scenario_clips,
    ClipPlanningError,
)

# Darshon: Transition this to a temporary directory so that it works with Vercel deployments (merge ongoing PR)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIM_OUTPUT_ROOT = os.environ.get(
    "MANIM_OUTPUT_ROOT", os.path.join(_REPO_ROOT, "output", "manim_runs")
)


# Function to generate a unique identifier (UUID) associated with each request to ensure that files are uniquely named and avoid conflicts
def generate_uuid():
    return str(uuid.uuid4())


# Function to delete local files after processing to clean up the server storage
def delete_local_files(file_paths):
    for file_path in file_paths:
        os.remove(file_path)
        print(f"Successfully deleted {file_path}")


def setup_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if url is None or key is None:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in the environment"
        )

    supabase_client = create_client(supabase_url=url, supabase_key=key)

    return supabase_client


# This function is a helper function that encapsulates the logic for generating character images. It is called by the /generate_character_images endpoint and can also be used for retrying character image generation.
def generate_character_images_impl(
    script: dict[str, Any], request_id: str, retry_image_id: str | None = None
) -> tuple[dict[str, str], list[str | None], list[str]]:

    (
        character_image_file_mapping,
        character_uploaded_file_names,
        character_json_file_paths,
    ) = generate_characters(script, request_id, retry_image_id)

    return (
        character_image_file_mapping,
        character_uploaded_file_names,
        character_json_file_paths,
    )


def get_image_roots() -> list[Path]:
    tmp = Path(tempfile.gettempdir())
    return [
        tmp / "Background_Image_Output",
        tmp / "Character_Image_Output",
    ]


def get_video_roots() -> list[Path]:
    tmp = Path(tempfile.gettempdir())
    return [
        Path(
            MANIM_OUTPUT_ROOT
        ),  # Darshon: Transition this to a temporary directory so that it works with Vercel deployments (merge ongoing PR)
        tmp / "Video_Generation_Pipeline",
    ]


def file_path_guard(raw_path: str, roots: list[Path]) -> Path:
    """Map a client-supplied path to a real file inside one of `roots`.

    Two things are going on. The frontend builds these URLs as
    `/api/image/<absolute server path>`, which strips the leading slash --
    so the path arrives relative -> restore the slash before resolving.

    And resolving alone is not enough: FileResponse on an unchecked path
    serves any file the backend can read, so the
    resolved path must be confined to a known output directory.
    """
    candidate = Path(raw_path if raw_path.startswith("/") else "/" + raw_path)

    try:
        candidate = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail="File not found")

    for root in roots:
        try:
            candidate.relative_to(root.resolve())
        except (ValueError, OSError):
            continue
        if candidate.is_file():
            return candidate

    raise HTTPException(
        status_code=403,
        detail="Path is outside the served media directories or is not a file",
    )


# This function is a helper function that returns the path to the status.json file for a given request_id. It is used to track the progress of video generation tasks.
def video_status_path(request_id: str) -> str:
    """Return the path to the status.json file for a given request_id."""
    return os.path.join(
        tempfile.gettempdir(), "Video_Run_Status", request_id, "status.json"
    )


# This function writes the status of the video generation process to a status.json file. It ensures that the write operation is atomic, preventing concurrent reads from observing a partially written file.
def write_video_status(request_id: str, status: dict) -> None:
    """Write status.json atomically — write to a sibling temp file then
    os.replace() over the real path, so a concurrent /video_status read can
    never observe a truncated/partial write mid-json.dump (reproduced during
    real testing: a poll landing mid-write raised JSONDecodeError)."""

    file_path = video_status_path(request_id)

    dir_path = Path(file_path).parent

    dir_path.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=dir_path
    ) as tmp_file:
        json.dump(status, tmp_file, indent=2)
        tmp_file.flush()

    os.replace(tmp_file.name, file_path)


# This function creates a callback function that is called when a scene is completed during video generation. It updates the status dictionary with the results of the scene and writes the updated status to the status.json file.
def make_on_scene_complete_callback(
    status: dict, request_id: str
) -> Callable[[dict], None]:
    def on_scene_complete(result: dict) -> None:
        """Callback function to be called when a scene is completed."""
        scene_id = str(result["scene_id"])

        if result["success"]:
            status["completed_scenes"][scene_id] = result["output_file"]
        else:
            status["failed_scenes"][scene_id] = result["error"]

        write_video_status(request_id, status)

    return on_scene_complete


# This function runs the video generation process in the background. It plans clips for every scene, renders each scene through Veo, and writes the status to a status.json file after every stage/scene transition. If any unexpected failure occurs, it leaves the status.json in a terminal "failed" state rather than letting the background thread die silently.
def run_video_generation(
    script: dict,
    request_id: str,
    background_image_path: str,
    character_image_file_mapping: dict,
) -> None:
    """Background job: plan clips for every scene, then render each scene
    through the chosen character-video backend. Writes status.json after every
    stage/scene transition so /video_status can report progress without
    blocking on the whole run. Any unexpected failure still leaves status.json
    in a terminal "failed" state rather than letting the background thread die
    silently.
    """
    status = {"state": "planning_clips", "completed_scenes": {}, "failed_scenes": {}}
    write_video_status(request_id, status)

    output_dir = Path(tempfile.gettempdir()) / "Video_Generation_Pipeline" / request_id

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        client = setup_gemini_client()

        planned_scenario = plan_scenario_clips(script, client=client)

        status["state"] = "rendering"

        write_video_status(request_id, status)

        on_scene_complete = make_on_scene_complete_callback(status, request_id)

        run_scenario_pipeline_solo_clip(
            client=client,
            scenario=planned_scenario,
            character_image_file_mapping=character_image_file_mapping,
            background_image_path=background_image_path,
            output_dir=output_dir,
            model="veo-3.1-fast-generate-preview",
            on_scene_complete=on_scene_complete,
        )

        status["state"] = (
            "done" if not status["failed_scenes"] else "completed_with_errors"
        )
        write_video_status(request_id, status)

    except ClipPlanningError as e:
        status["state"] = "failed"
        status["error"] = f"clip planning failed: {e}"
        write_video_status(request_id, status)

    except Exception as e:
        status["state"] = "failed"
        status["error"] = str(e)
        write_video_status(request_id, status)
        print(
            f"[generate_videos_v2] request {request_id} failed:\n{traceback.format_exc()}"
        )
