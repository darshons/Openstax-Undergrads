# full_scene_test.py
#
# Runs one full scene through the real stitching pipeline (first clip +
# extensions, not isolated first-clips like director_experiment.py) using the
# two variants that held up in testing: V2 (singles framing) on single-speaker
# clips, V1 (silent-partner text) on multi-speaker clips. V3 is excluded -
# it invented dialogue on short lines and was dropped.
#
# Usage:
#   python full_scene_test.py --scene-id 1                       # preview prompts only, no API calls
#   python full_scene_test.py --scene-id 1 --mode generate        # spends real Veo credits
#
import argparse
import os

from director_experiment import (
    SILENT_PARTNER_INSTRUCTION,
    _char_lookup,
    _framing_reinforcement,
    _singles_camera,
)
from video_generator.cli import load_env
from video_generator.pipeline import run_scene_pipeline
from video_generator.prompt_builder import build_veo_prompt
from video_generator.scenario_loader import load_scenario
from video_generator.veo_api import REFERENCE_IMAGES, VEO_MODELS


def build_scene_clip_prompts(
    scene: dict, characters: list, visual_style: str, variant_mode: str = "auto"
) -> list:
    """One prompt per clip, in order.

    variant_mode:
        "auto"   - V2 (singles framing) on single-speaker clips, V1 (silent-partner
                   text) on multi-speaker clips - the hybrid validated in testing.
        "v1_all" - V1 applied uniformly to every clip with dialogue, camera left
                   as originally authored (no singles-framing override).
    """
    lookup = _char_lookup(characters)
    shared_audio = scene.get("audio", {})
    clips = scene["clips"]
    prompts = []

    for i, clip in enumerate(clips):
        dialogue = clip.get("dialogue", [])
        speaker_ids = {d["character_id"] for d in dialogue}
        camera = clip.get("camera") or scene.get("camera", {})
        use_singles_framing = variant_mode == "auto" and len(speaker_ids) == 1

        if use_singles_framing:
            speaker_id = next(iter(speaker_ids))
            speaker = lookup[speaker_id]
            others = [c for c in characters if c["character_id"] != speaker_id]
            other_name = others[0]["name"] if others else ""
            camera = _singles_camera(speaker["name"], other_name)

        clip_scene = {
            "setting": clip.get("setting", scene.get("setting", "")),
            "character_actions": clip.get(
                "character_actions", scene.get("character_actions", "")
            ),
            "camera": camera,
            "audio": {
                "dialogue": dialogue,
                "sound_effects": clip.get(
                    "sound_effects", shared_audio.get("sound_effects", "none")
                ),
                "ambience": clip.get("ambience", shared_audio.get("ambience", "none")),
            },
        }
        if i == len(clips) - 1 and scene.get("on_screen_text"):
            clip_scene["on_screen_text"] = scene["on_screen_text"]

        prompt = build_veo_prompt(
            clip_scene, characters, visual_style, is_continuation=(i > 0)
        )

        if use_singles_framing:
            other_name = others[0]["name"] if others else ""
            if other_name:
                prompt = f"{prompt}\n\n{_framing_reinforcement(other_name)}"
            variant = "v2_singles_framing"
        elif dialogue:
            prompt = f"{prompt}\n\n{SILENT_PARTNER_INSTRUCTION}"
            variant = "v1_silent_partner"
        else:
            variant = "v0_baseline (no dialogue in this clip)"

        print(f"  clip {i + 1}: {len(dialogue)} line(s), speakers={speaker_ids} -> {variant}")
        prompts.append(prompt)

    return prompts


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Generate one full scene using V1/V2 director tricks.")
    parser.add_argument("--scenario", default="scenario.json")
    parser.add_argument("--scene-id", type=int, required=True)
    parser.add_argument("--mode", choices=["preview", "generate"], default="preview")
    parser.add_argument("--model-key", choices=list(VEO_MODELS), default="veo-3.1-fast")
    parser.add_argument("--variant", choices=["auto", "v1_all"], default="auto")
    parser.add_argument("--verify-clips", action="store_true")
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    args = parser.parse_args()

    scenario = load_scenario(args.scenario)
    scene = next(s for s in scenario["scenes"] if s["scene_id"] == args.scene_id)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]

    print(f"\nSCENE {args.scene_id} - assigning variant per clip ({args.variant}):")
    clip_prompts = build_scene_clip_prompts(scene, characters, visual_style, variant_mode=args.variant)

    if args.mode == "preview":
        for i, p in enumerate(clip_prompts, start=1):
            print(f"\n{'='*70}\nCLIP {i}\n{'='*70}\n{p}\n")
        return

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return

    from google import genai

    client = genai.Client(api_key=args.api_key)
    final_path = run_scene_pipeline(
        client=client,
        scene_id=args.scene_id,
        clip_prompts=clip_prompts,
        reference_images=REFERENCE_IMAGES or None,
        verify_clips=args.verify_clips,
        scene=scene,
        characters=characters,
        model=VEO_MODELS[args.model_key],
    )
    print(f"\nDone: {final_path}")


if __name__ == "__main__":
    main()
