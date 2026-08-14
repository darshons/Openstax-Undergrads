from fastapi import APIRouter, HTTPException
from storage3.exceptions import StorageApiError

from API.instructor_api_helpers import setup_supabase_client

# API router instance to define the endpoints for the FastAPI application for the student
student_router = APIRouter()


# This endpoint will be called by the frontend to retrieve the generated assets to display them in the frontend
@student_router.get("/assets/{project_id:path}")
def get_assets(project_id: str):
    supabase_client = setup_supabase_client()

    try:

        video_list = supabase_client.storage.from_("Videos").list(project_id)

        if not video_list or len(video_list) == 0:
            raise HTTPException(
                status_code=404, detail=f"No assets found for project_id: {project_id}"
            )

        video_links = dict()

        for video in video_list:
            video_links[video["name"]] = supabase_client.storage.from_(
                "Videos"
            ).get_public_url(f"{project_id}/{video['name']}")

        script_link = supabase_client.storage.from_("Scripts").get_public_url(
            f"{project_id}/script.json"
        )

        return {
            "message": "Assets retrieved successfully",
            "script_link": script_link,
            "video_links": video_links,
        }

    except StorageApiError as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving assets: {str(e)}"
        )
