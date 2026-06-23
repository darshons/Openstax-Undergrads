#test_prompts.py - free check, builds prompts without calling Veo
from stitch_videos import build_clip_prompts
from video_gen import load_scenario

scenario = load_scenario("scenario.json")
characters = scenario["characters"]
visual_style = scenario["visual_style"]

scene = next(s for s in scenario["scenes"] if s["scene_id"] == 2)
prompts = build_clip_prompts(scene, characters, visual_style)

print(f"scene {scene['scene_id']}: {len(prompts)} clips\n")
for i, p in enumerate(prompts, start=1):
    print(f"{'='*60}\nCLIP {i}\n{'='*60}\n{p}\n")