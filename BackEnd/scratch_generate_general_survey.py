import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv("backend.env")
from google import genai

from Video_Generation_Pipeline.video_generator.solo_clip_pipeline import run_scenario_pipeline_solo_clip

SCRIPT_PATH = "Video_Generation_Pipeline/general_survey_script_with_clips.json"
REF_IMAGES_DIR = Path("Video_Generation_Pipeline/reference_images_general_survey")
OUTPUT_DIR = Path("Video_Generation_Pipeline/output/general_survey")

with open(SCRIPT_PATH) as f:
    scenario = json.load(f)

character_image_file_mapping = {
    c["character_id"]: str(REF_IMAGES_DIR / f"{c['character_id']}.png")
    for c in scenario["characters"]
}
background_image_path = str(REF_IMAGES_DIR / "background_reference_image.png")

api_key = os.environ["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)


def on_scene_complete(result):
    if result["success"]:
        print(f"  scene {result['scene_id']} DONE -> {result['output_file']}")
    else:
        print(f"  scene {result['scene_id']} FAILED: {result['error']}")


print(f"Generating {len(scenario['scenes'])} scenes (solo-clip, veo-3.1-fast)...")
results = run_scenario_pipeline_solo_clip(
    client=client,
    scenario=scenario,
    character_image_file_mapping=character_image_file_mapping,
    background_image_path=background_image_path,
    output_dir=OUTPUT_DIR,
    model="veo-3.1-fast-generate-preview",
    on_scene_complete=on_scene_complete,
)

print("\nFINAL RESULTS:")
print(json.dumps(results, indent=2))

failed = [r for r in results if not r["success"]]
if failed:
    print(f"\n{len(failed)} scene(s) failed.")
    sys.exit(1)
