import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from google import genai

from Video_Generation_Pipeline.video_generator.clip_planner import plan_scenario_clips
from Video_Generation_Pipeline.video_generator.solo_clip_pipeline import run_scenario_pipeline_solo_clip

SCRIPT_PATH = "Script_Generation_Pipeline/_Script_Outputs/output_script_with_decision_points_anthropic_new.json"
REF_IMAGES_DIR = Path("Video_Generation_Pipeline/reference_images_finding_right_words")
OUTPUT_DIR = Path("/private/tmp/claude-501/-Users-justinlee-projects-Openstax-Undergrads/c482516d-0725-4cc0-83d7-b495952be15c/scratchpad/prod_pipeline_test")

with open(SCRIPT_PATH) as f:
    script = json.load(f)

# Trim to just scene 1 to keep this test cheap.
script["scenes"] = [s for s in script["scenes"] if s["scene_id"] == 1]

character_image_file_mapping = {
    c["character_id"]: str(REF_IMAGES_DIR / f"{c['character_id']}.png")
    for c in script["characters"]
}
background_image_path = str(REF_IMAGES_DIR / "background_reference_image.png")

api_key = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=api_key)

print("Planning clips (plan_scenario_clips)...")
planned = plan_scenario_clips(script, client=client)
print(json.dumps(planned["scenes"][0]["clips"], indent=2))

print("\nRendering via run_scenario_pipeline_solo_clip...")


def on_scene_complete(result):
    print(f"  scene {result['scene_id']} complete: {result}")


results = run_scenario_pipeline_solo_clip(
    client=client,
    scenario=planned,
    character_image_file_mapping=character_image_file_mapping,
    background_image_path=background_image_path,
    output_dir=OUTPUT_DIR,
    model="veo-3.1-fast-generate-preview",
    on_scene_complete=on_scene_complete,
)

print("\nFINAL RESULTS:")
print(json.dumps(results, indent=2))
