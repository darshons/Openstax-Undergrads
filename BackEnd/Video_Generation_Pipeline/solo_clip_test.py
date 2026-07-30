# solo_clip_test.py
#
# Generates one isolated clip per dialogue line, showing ONLY the speaking
# character in frame - the other character does not appear in the shot at
# all (not backgrounded, not a silhouette). Each line is its own independent
# "first clip" generation call, primed by reference images, meant to be
# manually stitched together in post rather than chained via Veo's
# extension mechanism.
#
# This is the most aggressive version of what V2 (singles framing, background
# silhouette allowed) and V3 (one speaker per clip, grouped by speaker run)
# already tested: every dialogue line across the whole scene becomes its own
# solo clip, not just alternating multi-turn lines. Since Veo never has to
# render two characters in the same shot, it can't put dialogue in the wrong
# mouth - the tradeoff is that continuity/blocking between lines is handled
# entirely in manual editing afterward, not by Veo.
#
# Short lines get the no-invent guard (from scene2_real_cut_test.py) since
# generating them in isolation risks Veo inventing extra dialogue to fill the
# forced 8s runtime.
#
# Usage:
#   python solo_clip_test.py --scene-id 1 --mode preview
#   python solo_clip_test.py --scene-id 1 --mode generate
#
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from director_experiment import _char_lookup, _resolve_clip_scene
from video_generator.cli import load_env
from video_generator.prompt_builder import build_veo_prompt
from video_generator.scenario_loader import load_scenario
from video_generator.veo_api import (
    REFERENCE_IMAGES,
    VEO_MODELS,
    RESOLUTION,
    generate_first_clip,
    download_video,
    estimate_cost,
)

_TRANSCRIPT_EVAL_ROOT = Path(__file__).resolve().parent.parent / "Transcript_Eval_Pipeline"
if str(_TRANSCRIPT_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TRANSCRIPT_EVAL_ROOT))
from transcript_eval.eval import evaluate_clip  # noqa: E402

OUTPUT_ROOT = Path(__file__).resolve().parent / "output" / "what_do_you_say_next" / "raw"
FIRST_CLIP_SECONDS = 8


def _output_dir(scene_id: int) -> Path:
    """Scene-scoped output dir - clip_id numbering restarts at 1 for every
    scene, so a shared flat directory causes filename collisions across
    scenes (e.g. scene 1 clip 1 and scene 2 clip 1 both land on '01_...')."""
    return OUTPUT_ROOT / f"scene{scene_id}"

NO_INVENT_INSTRUCTION = (
    "Do not invent, add, or extend any spoken dialogue beyond the single line "
    "specified above. After delivering this line, {name} says nothing further - "
    "no additional speech - and simply reacts naturally (a small gesture, "
    "posture shift, or expression change) for the rest of the clip."
)
SHORT_LINE_WORD_LIMIT = 5

# Fixed per-character pose and camera, reused identically across every solo
# clip in every scene (not derived from each clip's character_actions, which
# describe one-off blocking like "enters from the left" or "arms tighten").
# The goal is pixel-level-as-possible consistency of background and body
# position across cuts - only facial expression is left free to vary with
# the line's emotional content, per the user's call.
CHARACTER_BASE_POSE = {
    "nurse_maya": (
        "Maya stands beside Carl's hospital bed, weight settled evenly on both "
        "feet, hands relaxed at her sides, body angled slightly toward the bed. "
        "This exact standing position and stance is identical in every shot of "
        "Maya in this scene - she does not enter, walk, or change position."
    ),
    "patient_carl": (
        "Carl sits upright in the hospital bed, propped against the pillow, "
        "forearms resting loosely on the blanket in front of him. This exact "
        "seated position is identical in every shot of Carl in this scene - he "
        "does not shift position in the bed."
    ),
}

# Each character gets their own distinct, fixed backdrop - not the same
# generic "hospital room" behind both of them. The point is that cutting
# between characters should read as two different camera setups in the room
# (what's actually visible behind each person), while staying identical
# across that same character's own clips.
CHARACTER_BASE_BACKGROUND = {
    "nurse_maya": (
        "Directly behind Maya: the window with soft daylight and curtains, and "
        "the bedside table holding the water pitcher and glasses, positioned "
        "over her shoulder. The vitals monitor and IV pole are NOT visible in "
        "Maya's shots - they are out of frame behind the camera."
    ),
    "patient_carl": (
        "Directly behind Carl: the vitals monitor on its wall mount or stand "
        "and the IV pole beside the bed, with the raised head of the hospital "
        "bed. The window and curtains are NOT visible in Carl's shots - they "
        "are out of frame behind the camera."
    ),
}

CHARACTER_BASE_CAMERA = {
    "nurse_maya": {
        "angle": (
            "Static medium shot on Maya only, framed from the waist up, camera "
            "at her eye level, Maya centered in frame. This exact camera "
            "distance, height, and angle is identical in every shot of Maya in "
            f"this scene. {CHARACTER_BASE_BACKGROUND['nurse_maya']}"
        ),
        "movement": "Static.",
        "lens_effect": "Shallow depth of field, neutral warm tone, identical lighting in every shot.",
    },
    "patient_carl": {
        "angle": (
            "Static medium shot on Carl only, framed from the waist up as he "
            "sits in bed, camera at his eye level, Carl centered in frame. This "
            "exact camera distance, height, and angle is identical in every "
            f"shot of Carl in this scene. {CHARACTER_BASE_BACKGROUND['patient_carl']}"
        ),
        "movement": "Static.",
        "lens_effect": "Shallow depth of field, neutral warm tone, identical lighting in every shot.",
    },
}


def _solo_camera(speaker_id: str) -> dict:
    return CHARACTER_BASE_CAMERA[speaker_id]


def _solo_reinforcement(speaker_name: str, other_name: str) -> str:
    return (
        f"{other_name} is not in this shot, full stop - not their face, not "
        f"their back, not their shoulder or hair, not a blurry or out-of-focus "
        f"shape, not any part of them anywhere in frame at any point in the "
        f"clip. Treat this as though {speaker_name} is alone in the room for "
        "filming purposes, even though the scene setting describes both "
        "characters present.\n\n"
        f"Background and pose consistency: the camera framing, backdrop, and "
        f"{speaker_name}'s body position must look identical to every other "
        f"shot of {speaker_name} in this scene - same camera distance and "
        f"angle, same pose, same specific objects visible behind them. This is "
        f"a different, distinct camera setup from {other_name}'s shots - "
        f"{speaker_name}'s backdrop should NOT look like {other_name}'s "
        f"backdrop. Only {speaker_name}'s facial expression is free to vary "
        "naturally with what they are saying."
    )


def build_solo_clip_prompts(scene: dict, characters: list, visual_style: str) -> list:
    """One entry per dialogue line across every clip in the scene, in original
    order. Returns list of dicts: label, clip_id, speaker_id, line, prompt.

    Pose, camera, and background are held fixed per-character (CHARACTER_BASE_POSE /
    CHARACTER_BASE_CAMERA) rather than pulled from each clip's one-off
    character_actions text, so cuts back to the same character look like the
    same shot instead of a new composition each time. Only facial expression
    is left to vary with the line's content.
    """
    lookup = _char_lookup(characters)
    entries = []

    for clip in scene["clips"]:
        clip_scene = _resolve_clip_scene(scene, clip)
        dialogue = clip_scene["audio"]["dialogue"]

        for line_idx, line in enumerate(dialogue):
            speaker_id = line["character_id"]
            speaker = lookup[speaker_id]
            others = [c for c in characters if c["character_id"] != speaker_id]
            other_name = others[0]["name"] if others else ""

            line_scene = {
                "setting": scene.get("setting", ""),
                "character_actions": CHARACTER_BASE_POSE[speaker_id],
                "camera": _solo_camera(speaker_id),
                "audio": {**clip_scene["audio"], "dialogue": [line]},
            }
            prompt = build_veo_prompt(line_scene, characters, visual_style, is_continuation=False)
            if other_name:
                prompt = f"{prompt}\n\n{_solo_reinforcement(speaker['name'], other_name)}"

            word_count = len(line["line"].split())
            guarded = word_count <= SHORT_LINE_WORD_LIMIT
            if guarded:
                prompt = f"{prompt}\n\n{NO_INVENT_INSTRUCTION.format(name=speaker['name'])}"

            entries.append(
                {
                    "label": f"clip{clip['clip_id']}_line{line_idx + 1}_{speaker_id}",
                    "clip_id": clip["clip_id"],
                    "speaker_id": speaker_id,
                    "speaker_name": speaker["name"],
                    "line": line["line"],
                    "word_count": word_count,
                    "guarded": guarded,
                    "prompt": prompt,
                }
            )

    return entries


def preview(scene: dict, characters: list, visual_style: str):
    entries = build_solo_clip_prompts(scene, characters, visual_style)
    for i, e in enumerate(entries, start=1):
        guard_note = " [no-invent guard]" if e["guarded"] else ""
        print(
            f"\n{'='*70}\n{i:02d}  {e['label']}  ({e['word_count']} words){guard_note}\n"
            f"    \"{e['line']}\"\n{'='*70}\n{e['prompt']}\n"
        )
    print(f"\n{len(entries)} solo clips would be generated, {FIRST_CLIP_SECONDS}s each.")


def generate(scene: dict, characters: list, visual_style: str, model_key: str, api_key: str, only=None):
    from google import genai

    client = genai.Client(api_key=api_key)
    all_entries = build_solo_clip_prompts(scene, characters, visual_style)
    reference_images = REFERENCE_IMAGES or None
    model_api_name = VEO_MODELS[model_key]

    indexed_entries = list(enumerate(all_entries, start=1))
    if only:
        indexed_entries = [(i, e) for i, e in indexed_entries if i in only]

    total_cost = estimate_cost(model_key, RESOLUTION, FIRST_CLIP_SECONDS) * len(indexed_entries)
    print(f"\nAbout to generate {len(indexed_entries)} solo clips (~${total_cost:.2f} total, {model_key}).")

    output_dir = _output_dir(scene["scene_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for i, e in indexed_entries:
        video_path = str(output_dir / f"{i:02d}_{e['label']}.mp4")
        print(f"\n{'-'*70}\n{i:02d}  {e['label']}  \"{e['line']}\"\n{'-'*70}")

        start = time.time()
        error = None
        report = None
        try:
            video_obj, attempts = generate_first_clip(
                client,
                e["prompt"],
                reference_images=reference_images,
                duration_seconds=FIRST_CLIP_SECONDS,
                model=model_api_name,
            )
            download_video(client, video_obj, video_path)
            report = evaluate_clip(
                client=client,
                video_path=video_path,
                scene_id=scene["scene_id"],
                clip_id=e["label"],
                dialogue=[{"character_id": e["speaker_id"], "line": e["line"]}],
                characters=characters,
            )
        except Exception as exc:
            error = str(exc)
            print(f"  ERROR: {error}")

        wall_time = time.time() - start
        attribution_passed = (
            report["speaker_attribution"]["attribution_passed"]
            if report and report["speaker_attribution"]
            else None
        )
        dialogue_passed = report["dialogue_match"]["passed"] if report else None
        if error:
            status = "ERROR"
        elif dialogue_passed is False:
            status = "FAIL(dialogue)"
        elif attribution_passed is False:
            status = "FAIL(speaker)"
        elif attribution_passed:
            status = "PASS"
        else:
            status = "ERROR"
        print(f"  {status}  ({wall_time:.0f}s)")

        results.append({**e, "video_path": video_path if Path(video_path).exists() else None,
                         "attribution_passed": attribution_passed, "dialogue_passed": dialogue_passed, "error": error, "status": status})

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for i, r in enumerate(results, start=1):
        print(f"  [{r['status']:14s}] {i:02d}_{r['label']}")
    print(f"\nClips saved to: {output_dir}")
    print("Stitch order = numeric filename prefix (01, 02, 03, ...).")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate solo (single-character) clips, one per dialogue line, for manual stitching.")
    parser.add_argument("--scenario", default="scenario.json")
    parser.add_argument("--scene-id", type=int, required=True)
    parser.add_argument("--mode", choices=["preview", "generate"], default="preview")
    parser.add_argument("--model-key", choices=list(VEO_MODELS), default="veo-3.1-fast")
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated 1-based clip indices to (re)generate, e.g. '3,6' (default: all).",
    )
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    scenario = load_scenario(args.scenario)
    scene = next(s for s in scenario["scenes"] if s["scene_id"] == args.scene_id)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]

    if args.mode == "preview":
        preview(scene, characters, visual_style)
        return

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return
    only = {int(x) for x in args.only.split(",")} if args.only else None
    generate(scene, characters, visual_style, args.model_key, args.api_key, only=only)


if __name__ == "__main__":
    main()
