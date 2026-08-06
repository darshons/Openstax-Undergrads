# scene2_real_cut_test.py
#
# Scene 2 is one authored clip with two alternating speakers (Maya's long
# line, then Carl's two-word reply "Mm. Okay."). Generated as one continuous
# shot (V1 text-only fix), it visually resolved the speaker swap by warping/
# swapping the characters' positions instead of cutting - a real cut is the
# only reliable fix for that.
#
# A real cut was tried before as "V3" and dropped: splitting a clip into one
# generation call per speaker made Veo invent extra dialogue to fill the
# runtime when the assigned line was very short. This script retries the real
# cut for scene 2 specifically, with an explicit guard against that: the
# short-line clip is told not to invent dialogue and to react silently
# instead.
#
# Usage:
#   python scene2_real_cut_test.py --mode preview
#   python scene2_real_cut_test.py --mode generate
#
import argparse
import os

from director_experiment import _char_lookup, _framing_reinforcement, _singles_camera
from video_generator.cli import load_env
from video_generator.pipeline import run_scene_pipeline
from video_generator.prompt_builder import build_veo_prompt
from video_generator.scenario_loader import load_scenario
from video_generator.veo_api import REFERENCE_IMAGES, VEO_MODELS

NO_INVENT_INSTRUCTION = (
    "Do not invent, add, or extend any spoken dialogue beyond the single line "
    "specified above. After delivering this line, {name} says nothing further - "
    "no additional speech - and simply reacts naturally (a small gesture, "
    "posture shift, or expression change) for the rest of the clip."
)


def build_real_cut_prompts(scene: dict, characters: list, visual_style: str) -> list:
    clip = scene["clips"][0]
    dialogue = clip["dialogue"]
    lookup = _char_lookup(characters)

    prompts = []
    for i, line in enumerate(dialogue):
        speaker_id = line["character_id"]
        speaker = lookup[speaker_id]
        others = [c for c in characters if c["character_id"] != speaker_id]
        other_name = others[0]["name"] if others else ""

        clip_scene = {
            "setting": clip.get("setting", scene.get("setting", "")),
            "character_actions": clip.get("character_actions", scene.get("character_actions", "")),
            "camera": _singles_camera(speaker["name"], other_name),
            "audio": {
                "dialogue": [line],
                "sound_effects": clip.get("sound_effects", scene.get("audio", {}).get("sound_effects", "none")),
                "ambience": clip.get("ambience", scene.get("audio", {}).get("ambience", "none")),
            },
        }
        prompt = build_veo_prompt(clip_scene, characters, visual_style, is_continuation=(i > 0))
        if other_name:
            prompt = f"{prompt}\n\n{_framing_reinforcement(other_name)}"

        word_count = len(line["line"].split())
        if word_count <= 5:
            prompt = f"{prompt}\n\n{NO_INVENT_INSTRUCTION.format(name=speaker['name'])}"

        print(f"  sub-clip {i}: {speaker['name']} ({word_count} words) -> \"{line['line']}\"")
        prompts.append(prompt)

    return prompts


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Real-cut retry for scene 2 with a no-invented-dialogue guard.")
    parser.add_argument("--mode", choices=["preview", "generate"], default="preview")
    parser.add_argument("--model-key", choices=list(VEO_MODELS), default="veo-3.1-fast")
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    args = parser.parse_args()

    scenario = load_scenario("scenario.json")
    scene = next(s for s in scenario["scenes"] if s["scene_id"] == 2)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]

    print("\nSCENE 2 real-cut split:")
    clip_prompts = build_real_cut_prompts(scene, characters, visual_style)

    if args.mode == "preview":
        for i, p in enumerate(clip_prompts, start=1):
            print(f"\n{'='*70}\nSUB-CLIP {i}\n{'='*70}\n{p}\n")
        return

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return

    from google import genai

    client = genai.Client(api_key=args.api_key)
    final_path = run_scene_pipeline(
        client=client,
        scene_id=2,
        clip_prompts=clip_prompts,
        reference_images=REFERENCE_IMAGES or None,
        model=VEO_MODELS[args.model_key],
    )
    print(f"\nDone: {final_path}")


if __name__ == "__main__":
    main()
