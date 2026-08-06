import os, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv("backend.env")
from google import genai

from Video_Generation_Pipeline.video_generator.solo_clip_pipeline import _build_line_prompt, _extract_seed_frame
from Video_Generation_Pipeline.video_generator.character_rig import setting_summary
from Video_Generation_Pipeline.video_generator.veo_api import generate_first_clip, download_video

scenario = json.load(open("Video_Generation_Pipeline/anthony_scenario_script_with_clips.json"))
rig = json.load(open("Video_Generation_Pipeline/output/anthony_scenario/character_rig.json"))
scene = next(s for s in scenario["scenes"] if s["scene_id"] == 7)
setting_text = setting_summary(scenario)

line = scene["clips"][0]["dialogue"][0]  # instructor's line in scene 7, clip 1
prompt, speaker_id, _ = _build_line_prompt(scene, scenario["characters"], scenario["visual_style"], rig, line, setting_text)
print(prompt)

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# instructor already has an established look - seed from her most recent clip instead of reference images
seed_bytes = _extract_seed_frame(Path("Video_Generation_Pipeline/output/anthony_scenario/scene6_raw/01_instructor.mp4"))

video_obj, attempts = generate_first_clip(
    client, prompt, clip_index=1,
    seed_image_bytes=seed_bytes,
    duration_seconds=8,
    model="veo-3.1-fast-generate-preview",
)
download_video(client, video_obj, "Video_Generation_Pipeline/output/anthony_scenario/my_test_clip.mp4")
