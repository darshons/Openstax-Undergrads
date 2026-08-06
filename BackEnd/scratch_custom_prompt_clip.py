import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv("backend.env")
from google import genai

from Video_Generation_Pipeline.video_generator.veo_api import generate_first_clip, download_video

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# --- write your own prompt here ---
prompt = """Visual style: 2D semi-flat limited animation with dynamic but constrained movement.

Characters: Nurse Reyes (Supervising nurse): East Asian skin, Dark brown hair, Dark teal scrub top and grey scrub pants.

Setting: Outpatient clinic examination room, neutral beige walls, exam table, counter with sink.

Character actions: Standing, arms loosely at sides, facing slightly to the side.

Camera: Static medium shot, waist up, Nurse Reyes centered in frame.

Dialogue: Nurse Reyes: "Your custom line goes here."

Do not include any text overlays, captions, or subtitles."""

# --- pick ONE seeding mode ---

# Option A: reference images (character's first appearance, max 3 images)
reference_images = [
    "Video_Generation_Pipeline/reference_images_anthony/instructor.png",
    "Video_Generation_Pipeline/reference_images_anthony/background_reference_image.png",
]
seed_image_bytes = None

# Option B: seed from an existing clip's frame instead (comment out Option A above, uncomment this)
# from Video_Generation_Pipeline.video_generator.solo_clip_pipeline import _extract_seed_frame
# reference_images = None
# seed_image_bytes = _extract_seed_frame(Path("Video_Generation_Pipeline/output/anthony_scenario/scene6_raw/01_instructor.mp4"))

# --- generate ---
video_obj, attempts = generate_first_clip(
    client, prompt, clip_index=1,
    reference_images=reference_images,
    seed_image_bytes=seed_image_bytes,
    duration_seconds=8,
    model="veo-3.1-fast-generate-preview",
)
download_video(client, video_obj, "Video_Generation_Pipeline/output/anthony_scenario/my_test_clip.mp4")
