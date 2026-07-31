import os
import uuid
from typing import Any
import json
import traceback
import tempfile
from supabase import create_client, Client
from pathlib import Path
from collections.abc import Callable

from Script_Generation_Pipeline import setup_gemini_client

from Image_Generation_Pipeline import (
    generate_characters,
    generate_opening_frames,
)

from Video_Generation_Pipeline.video_generator.clip_planner import (
    plan_scenario_clips,
    ClipPlanningError,
)

from Video_Generation_Pipeline.video_generator.pipeline import (
    run_scenario_pipeline as run_veo_scenario_pipeline,
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


# This function is a helper function that encapsulates the logic for generating opening frames. It is called by the /generate_opening_frames endpoint and can also be used for retrying opening frame generation.
def generate_opening_frame_images_impl(
    script: dict[str, Any],
    background_image_path: str,
    character_image_file_mapping: dict[str, str],
    request_id: str,
    retry_image_id: str | None = None,
) -> tuple[dict[str, str], list[str | None], list[str]]:
    opening_scene_frame_file_mapping, uploaded_file_names, scene_json_file_paths = (
        generate_opening_frames(
            script,
            background_image_path,
            character_image_file_mapping,
            request_id,
            retry_image_id=retry_image_id,
        )
    )

    return opening_scene_frame_file_mapping, uploaded_file_names, scene_json_file_paths


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

    path = video_status_path(request_id)
    dir_path = Path(tempfile.gettempdir()) / "Video_Run_Status" / request_id

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=dir_path
    ) as tmp_file:
        json.dump(status, tmp_file, indent=2)
        tmp_file.flush()

    os.replace(tmp_file.name, path)


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
    script: dict, request_id: str, reference_images: list[str]
) -> None:
    """Background job: plan clips for every scene, then render each scene
    through Veo. Writes status.json after every stage/scene transition so
    /video_status can report progress without blocking on the whole run.
    Any unexpected failure still leaves status.json in a terminal "failed"
    state rather than letting the background thread die silently."""

    status = {"state": "planning_clips", "completed_scenes": {}, "failed_scenes": {}}
    write_video_status(request_id, status)

    try:
        client = setup_gemini_client()

        planned_scenario = plan_scenario_clips(script, client=client)

        status["state"] = "rendering"

        write_video_status(request_id, status)

        on_scene_complete = make_on_scene_complete_callback(status, request_id)

        run_veo_scenario_pipeline(
            client=client,
            scenario=planned_scenario,
            reference_images=reference_images or None,
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
            f"[generate_videos] request {request_id} failed:\n{traceback.format_exc()}"
        )
