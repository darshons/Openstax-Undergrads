import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from google import genai
from google.genai import types

from video_generator.veo_api import RESOLUTION, ASPECT_RATIO, download_video, poll_until_done
from solo_clip_finding_words import load_script, build_solo_clip_prompts
from video_generator.character_rig import load_cached_rig, rig_cache_path

SEEDS = {
    "nurse_maya": "/tmp/seed_scene2_0.png",
    "patient_harold": "/tmp/seed_harold_0.png",
    "charge_nurse_deb": "/tmp/seed_deb_0.png",
}

parser = argparse.ArgumentParser()
parser.add_argument("--scene-id", type=int, required=True)
parser.add_argument("--clip-index", type=int, required=True, help="0-based index into build_solo_clip_prompts entries")
parser.add_argument("--output-name", required=True)
args = parser.parse_args()

script = load_script()
scene = next(s for s in script["scenes"] if s["scene_id"] == args.scene_id)
rig = load_cached_rig(rig_cache_path(Path("output/finding_right_words/raw").parent))

entries = build_solo_clip_prompts(script, scene, rig)
entry = entries[args.clip_index]
print(f"Target clip: {entry['label']}  \"{entry['line']}\"")

seed_path = SEEDS[entry["speaker_id"]]
with open(seed_path, "rb") as f:
    seed_bytes = f.read()
print(f"Seed image: {seed_path}")

api_key = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=api_key)

output_path = f"output/finding_right_words/raw/scene{args.scene_id}/{args.output_name}"

operation = client.models.generate_videos(
    model="veo-3.1-fast-generate-preview",
    prompt=entry["prompt"],
    image=types.Image(image_bytes=seed_bytes, mime_type="image/png"),
    config=types.GenerateVideosConfig(
        aspect_ratio=ASPECT_RATIO,
        resolution=RESOLUTION,
        number_of_videos=1,
    ),
)
operation = poll_until_done(client, operation)
video_obj = operation.response.generated_videos[0].video
download_video(client, video_obj, output_path)
print(f"\nSUCCESS: saved to {output_path}")
