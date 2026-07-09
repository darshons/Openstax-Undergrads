import os
import uuid
from typing import Any

from Image_Generation_Pipeline import (
    generate_characters,
    generate_opening_frames,
)

from supabase import create_client, Client


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
