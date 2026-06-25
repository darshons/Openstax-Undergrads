#!/usr/bin/env python3
"""
Batch video generation runner.
Runs all experimental variations and steps away while it generates.
"""

import time
from pathlib import Path
from video_gen import (
    load_scenario,
    build_veo_prompt,
    generate_video,
    init_output_dir,
    VEO_MODELS,
)
import os


#SETTINGS
SCENARIO_FILE = "scenario.json"
API_KEY = os.environ.get("GEMINI_API_KEY")
RESOLUTION = "720p"
ASPECT_RATIO = "16:9"
RUNS_PER_MODEL = 3
REFERENCE_IMAGES = ["maya_reference.png", "carl_reference.png"]

#PROMPT VARIATIONS
PROMPT_VARIATIONS = {
    "baseline": "",
    "fix_line_swap": (
        "The character wearing light blue scrubs is Maya and speaks first. "
        "The character wearing a light green hospital gown is Carl and responds. "
        "Never swap their roles or voices."
    ),
    "fix_drift": (
        "Maintain exact character appearance from the first frame to the last. "
        "Maya always wears light blue scrubs. Carl always wears a light green hospital gown. "
        "No changes to their clothing, hair, skin tone, or facial features at any point."
    ),
    "fix_framing": (
        "Static medium two-shot. Both characters fully visible throughout. "
        "No cuts, no zooms, no camera movement."
    ),
    "fix_lipsync": (
        "Two characters have a calm, professional conversation. "
        "The nurse speaks with warmth and concern. "
        "The patient responds quietly and opens up emotionally."
    ),
    "fix_all": (
        "The character wearing light blue scrubs is Maya and speaks first. "
        "The character wearing a light green hospital gown is Carl and responds. "
        "Never swap their roles or voices. "
        "Maintain exact character appearance from the first frame to the last. "
        "No changes to their clothing, hair, skin tone, or facial features at any point. "
        "Static medium two-shot. Both characters fully visible throughout. "
        "No cuts, no zooms, no camera movement."
    ),
}

#BATCH DEFINITIONS
def build_batch(scenario):
    """Build the full list of generation jobs."""
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scenes = scenario["scenes"]
    scene3 = next(s for s in scenes if s["scene_id"] == 3)
    all_scenes = scenes
    jobs = []

    base_prompt = build_veo_prompt(scene3, characters, visual_style)

    #A: MULTI-RUN PER MODEL (scene 3, no sprites, baseline prompt)
    for model_key in VEO_MODELS.keys():
        for run in range(RUNS_PER_MODEL):
            jobs.append({
                "label": f"model_compare_{model_key}_run{run+1}",
                "scene": scene3,
                "model": model_key,
                "prompt_override": None,
                "reference_images": None,
            })

    #B: SPRITE VS NO SPRITE (scene 3, veo-3.1, baseline prompt)
    for run in range(RUNS_PER_MODEL):
        jobs.append({
            "label": f"sprite_test_WITH_run{run+1}",
            "scene": scene3,
            "model": "veo-3.1",
            "prompt_override": None,
            "reference_images": REFERENCE_IMAGES,
        })
        jobs.append({
            "label": f"sprite_test_WITHOUT_run{run+1}",
            "scene": scene3,
            "model": "veo-3.1",
            "prompt_override": None,
            "reference_images": None,
        })

    #C: PROMPT VARIATIONS (scene 3, veo-3.1, no sprites)
    for variation_name, variation_text in PROMPT_VARIATIONS.items():
        if variation_name == "baseline":
            continue #already covered in model compare
        override = base_prompt + f"\n\n{variation_text}"
        jobs.append({
            "label": f"prompt_variation_{variation_name}",
            "scene": scene3,
            "model": "veo-3.1",
            "prompt_override": override,
            "reference_images": None,
        })

    #D: FULL SCENARIO CONSISTENCY (all scenes, veo-3.1, sprite vs no sprite)
    for scene in all_scenes:
        for use_sprites in [True, False]:
            sprite_label = "WITH_sprites" if use_sprites else "NO_sprites"
            jobs.append({
                "label": f"full_scenario_scene{scene['scene_id']}_{sprite_label}",
                "scene": scene,
                "model": "veo-3.1",
                "prompt_override": None,
                "reference_images": REFERENCE_IMAGES if use_sprites else None,
            })

    return jobs, characters, visual_style


#RUNNER
def run_batch():
    if not API_KEY:
        print("ERROR: No GEMINI_API_KEY found in .env")
        return

    from google import genai
    client = genai.Client(api_key=API_KEY)
    init_output_dir()

    scenario = load_scenario(SCENARIO_FILE)
    jobs, characters, visual_style = build_batch(scenario)

    total = len(jobs)
    print(f"\nStarting batch: {total} generations")
    print(f"Estimated time: {total * 2}–{total * 3} minutes")
    print("─" * 60)

    succeeded = 0
    failed = 0

    for i, job in enumerate(jobs, 1):
        print(f"\n[{i}/{total}] {job['label']}")
        scene = job["scene"]
        prompt = build_veo_prompt(scene, characters, visual_style)

        result = generate_video(
            client=client,
            prompt=prompt,
            scene_id=scene["scene_id"],
            model_key=job["model"],
            resolution=RESOLUTION,
            aspect_ratio=ASPECT_RATIO,
            prompt_override=job["prompt_override"],
            reference_images=job["reference_images"],
        )

        if result["success"]:
            succeeded += 1
            #rename output file to include label for easy identification
            old_path = Path(result["output_file"])
            new_path = old_path.parent / f"{job['label']}_{old_path.name}"
            old_path.rename(new_path)
            print(f"✓ Saved as: {new_path.name}")
        else:
            failed += 1

        #small pause between generations to avoid rate limiting
        time.sleep(3)

    print(f"\n{'─'*60}")
    print(f"BATCH COMPLETE")
    print(f"✓ Succeeded: {succeeded} / {total}")
    print(f"✗ Failed:    {failed} / {total}")
    print(f"Output folder: output/")


if __name__ == "__main__":
    run_batch()