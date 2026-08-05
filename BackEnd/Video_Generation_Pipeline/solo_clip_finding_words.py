# solo_clip_finding_words.py
#
# Solo-clip generation (one isolated clip per dialogue line, only the
# speaking character ever in frame) for the "Finding the Right Words"
# lesson - a different scenario than scenario.json, with its own characters
# (Maya/Harold/Deb) and its own reference images
# (reference_images_finding_right_words/). Built on the same approach
# validated on the original lesson: fixed per-character pose, fixed
# per-character camera framing, and a distinct fixed backdrop per character
# so cuts between speakers read as two different camera setups in the same
# room rather than the same generic shot swapped between people.
#
# Difference from solo_clip_test.py: this script's source JSON has no
# per-scene "clips" breakdown (dialogue sits directly on each scene), and
# some of Harold's lines are bracketed non-verbal gestures like
# "[nods, then points left hand toward the pain scale]" rather than spoken
# text - those become silent reaction clips (no dialogue audio at all, and
# an explicit no-vocalization guard) instead of being sent to Veo as if they
# were a line to speak.
#
# Per-character pose/camera/backdrop is derived automatically by
# video_generator.character_rig (one cheap LLM call, cached to
# output/finding_right_words/character_rig.json) rather than hand-authored,
# the same mechanism used by solo_clip_test.py. Character portraits and the
# background reference image are likewise generated automatically by
# video_generator.reference_images (previously a manual scratch script run
# by hand before anything else could happen) - both are cheap, idempotent
# setup stages that only spend money on what's actually missing.
#
# Usage:
#   python solo_clip_finding_words.py --mode images                # generate+cache reference images, once per scenario
#   python solo_clip_finding_words.py --mode rig                   # derive+cache the rig, once per scenario
#   python solo_clip_finding_words.py --scene-id 1 --mode preview  # free, uses cached rig
#   python solo_clip_finding_words.py --scene-id 1 --mode generate
#
import argparse
import json
import os
import sys
import time
from pathlib import Path

from director_experiment import close_up_camera, interaction_isolation_instruction, references_interaction
from video_generator.character_rig import (
    generate_character_rig,
    load_cached_rig,
    rig_cache_path,
    save_rig_cache,
)
from video_generator.reference_images import ensure_reference_images
from video_generator.cli import load_env
from video_generator.prompt_builder import build_veo_prompt
from video_generator.veo_api import (
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

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "Script_Generation_Pipeline" / "_Script_Outputs"
    / "output_script_with_decision_points_anthropic_new.json"
)
REFERENCE_IMAGES_DIR = Path(__file__).resolve().parent / "reference_images_finding_right_words"
OUTPUT_ROOT = Path(__file__).resolve().parent / "output" / "finding_right_words" / "raw"
FIRST_CLIP_SECONDS = 8
SHORT_LINE_WORD_LIMIT = 5

NO_INVENT_INSTRUCTION = (
    "Do not invent, add, or extend any spoken dialogue beyond the single line "
    "specified above. After delivering this line, {name} says nothing further - "
    "no additional speech - and simply reacts naturally (a small gesture, "
    "posture shift, or expression change) for the rest of the clip."
)

NO_SPEECH_GESTURE_INSTRUCTION = (
    "{name} does not speak at all in this clip - lips stay closed, no "
    "vocalization, no words, no attempted speech sounds. Instead, {name} "
    "silently performs this specific action: {gesture}"
)

ROOM_REFERENCE_INSTRUCTION = (
    "A reference image of the empty hospital room is provided in addition to "
    "the character reference images. Match this room's exact wall color, "
    "furniture placement, whiteboard, monitor, IV pole, window, and lighting "
    "- do not redesign or reinterpret the room. The whiteboard shown in the "
    "reference has small handwritten notes on it that are illegible at this "
    "distance - keep the whiteboard exactly as shown in the reference "
    "(same faint illegible marks), do not add new legible words, numbers, or "
    "phrases to it, and do not render any other on-screen text anywhere in "
    "the shot."
)

def _character_names(characters: list) -> dict:
    return {c["character_id"]: c["name"] for c in characters}


def _other_character_reinforcement(speaker_id: str, other_ids: list, character_names: dict) -> str:
    speaker_name = character_names[speaker_id]
    other_names = [character_names[oid] for oid in other_ids]
    others_text = " or ".join(other_names) if other_names else ""
    lines = [
        f"{name} is not in this shot, full stop - not their face, not their "
        f"back, not their shoulder or hair, not a blurry or out-of-focus "
        f"shape, not any part of them anywhere in frame at any point in the "
        f"clip. Treat this as though {speaker_name} is alone in the room for "
        "filming purposes, even though the scene describes multiple people "
        "present."
        for name in other_names
    ]
    return (
        "\n\n".join(lines)
        + f"\n\nBackground and pose consistency: the camera framing, backdrop, "
        f"and {speaker_name}'s body position must look identical to every "
        f"other shot of {speaker_name} in this scene - same camera distance "
        f"and angle, same pose, same specific objects visible behind them. "
        f"This is a different, distinct camera setup from {others_text}'s "
        f"shots - {speaker_name}'s backdrop should NOT look like theirs. Only "
        f"{speaker_name}'s facial expression is free to vary naturally with "
        "what they are saying."
    )


def _is_gesture_only(line_text: str) -> bool:
    stripped = line_text.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def load_script() -> dict:
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _setting_text(script: dict) -> str:
    s = script.get("setting", {})
    return (
        f"{s.get('location', '')}. {s.get('scene_description', '')} "
        f"Lighting: {s.get('lighting', {}).get('source', '')}, "
        f"{s.get('lighting', {}).get('time_of_day', '')}."
    )


def build_solo_clip_prompts(script: dict, scene: dict, rig: dict) -> list:
    """One entry per dialogue line in the scene, in original order."""
    characters = script["characters"]
    visual_style = script["visual_style"]
    setting = _setting_text(script)
    all_ids = [c["character_id"] for c in characters]
    character_names = _character_names(characters)
    char_lookup = {c["character_id"]: c for c in characters}

    entries = []
    for line_idx, line in enumerate(scene["audio"]["dialogue"]):
        speaker_id = line["character_id"]
        other_ids = [cid for cid in all_ids if cid != speaker_id]
        gesture_only = _is_gesture_only(line["line"])
        interaction_flagged = not gesture_only and references_interaction(line["line"])

        camera = (
            close_up_camera(character_names[speaker_id], rig[speaker_id]["backdrop"])
            if interaction_flagged
            else rig[speaker_id]["camera"]
        )
        line_scene = {
            "setting": setting,
            "character_actions": rig[speaker_id]["pose"],
            "camera": camera,
            "audio": {
                "dialogue": [] if gesture_only else [line],
                "sound_effects": scene["audio"].get("sound_effects", "none"),
                "ambience": scene["audio"].get("ambience", "none"),
            },
        }
        # Only the speaker's own appearance is described here - the other
        # characters' full physical descriptions have no reason to be in a
        # prompt for a shot they're not supposed to appear in at all.
        prompt = build_veo_prompt(line_scene, [char_lookup[speaker_id]], visual_style, is_continuation=False)
        prompt = f"{prompt}\n\n{_other_character_reinforcement(speaker_id, other_ids, character_names)}\n\n{ROOM_REFERENCE_INSTRUCTION}"

        if interaction_flagged and other_ids:
            others_text = " or ".join(character_names[oid] for oid in other_ids)
            prompt = f"{prompt}\n\n{interaction_isolation_instruction(character_names[speaker_id], others_text)}"

        word_count = len(line["line"].split())
        guarded = False
        if gesture_only:
            gesture_text = line["line"].strip()[1:-1]
            prompt = f"{prompt}\n\n{NO_SPEECH_GESTURE_INSTRUCTION.format(name=character_names[speaker_id], gesture=gesture_text)}"
        elif word_count <= SHORT_LINE_WORD_LIMIT:
            guarded = True
            prompt = f"{prompt}\n\n{NO_INVENT_INSTRUCTION.format(name=character_names[speaker_id])}"

        entries.append(
            {
                "label": f"line{line_idx + 1}_{speaker_id}",
                "speaker_id": speaker_id,
                "speaker_name": character_names[speaker_id],
                "line": line["line"],
                "gesture_only": gesture_only,
                "interaction_flagged": interaction_flagged,
                "word_count": word_count,
                "guarded": guarded,
                "prompt": prompt,
            }
        )

    return entries


def _output_dir(scene_id: int) -> Path:
    return OUTPUT_ROOT / f"scene{scene_id}"


def _reference_images_for(speaker_id: str) -> list:
    """Veo caps reference images at 3 total. Each solo clip only ever shows
    one character, so we only need that character's portrait plus the room -
    2 images, well under the cap - instead of every character in the scene."""
    return [
        str(REFERENCE_IMAGES_DIR / f"{speaker_id}.png"),
        str(REFERENCE_IMAGES_DIR / "background_reference_image.png"),
    ]


def preview(script: dict, scene: dict, rig: dict):
    entries = build_solo_clip_prompts(script, scene, rig)
    for i, e in enumerate(entries, start=1):
        tag = " [GESTURE ONLY]" if e["gesture_only"] else " [no-invent guard]" if e["guarded"] else ""
        tag += " [interaction guard]" if e["interaction_flagged"] else ""
        print(
            f"\n{'='*70}\n{i:02d}  {e['label']}  ({e['word_count']} words){tag}\n"
            f"    \"{e['line']}\"\n{'='*70}\n{e['prompt']}\n"
        )
    print(f"\n{len(entries)} solo clips would be generated, {FIRST_CLIP_SECONDS}s each.")


def generate(script: dict, scene: dict, model_key: str, api_key: str, rig: dict, only=None):
    from google import genai

    client = genai.Client(api_key=api_key)
    characters = script["characters"]
    all_entries = build_solo_clip_prompts(script, scene, rig)
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
                reference_images=_reference_images_for(e["speaker_id"]),
                duration_seconds=FIRST_CLIP_SECONDS,
                model=model_api_name,
            )
            download_video(client, video_obj, video_path)
            if not e["gesture_only"]:
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
        dialogue_passed = report["dialogue_match"]["passed"] if report else None
        attribution_passed = (
            report["speaker_attribution"]["attribution_passed"]
            if report and report["speaker_attribution"]
            else None
        )
        if error:
            status = "ERROR"
        elif e["gesture_only"]:
            status = "GENERATED (gesture - review manually)"
        elif dialogue_passed is False:
            status = "FAIL(dialogue)"
        elif attribution_passed is False:
            status = "FAIL(speaker)"
        elif attribution_passed:
            status = "PASS"
        else:
            status = "ERROR"
        print(f"  {status}  ({wall_time:.0f}s)")

        results.append({**e, "video_path": video_path if Path(video_path).exists() else None, "status": status})

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for i, r in enumerate(results, start=1):
        print(f"  [{r['status']:30s}] {i:02d}_{r['label']}")
    print(f"\nClips saved to: {output_dir}")
    print("Stitch order = numeric filename prefix (01, 02, 03, ...).")
    return results


def run_full_lesson(script: dict, model_key: str, api_key: str, rig: dict):
    """The Option B orchestrator: generate + stitch every scene in the
    script in one pass, instead of invoking --scene-id by hand per scene.
    Each scene gets its own stitched output file (scenes are branch points
    in an interactive lesson, not a linear sequence to concatenate into one
    video)."""
    from stitch_solo_clips import _default_output_path, stitch

    scenes = script["scenes"]
    print(f"\n{'#'*70}\nFULL LESSON: {len(scenes)} scenes\n{'#'*70}")

    scene_reports = []
    for scene in scenes:
        scene_id = scene["scene_id"]
        print(f"\n{'='*70}\nSCENE {scene_id}\n{'='*70}")
        results = generate(script, scene, model_key, api_key, rig)
        needs_review = [r for r in results if r["status"] != "PASS"]

        clips_dir = _output_dir(scene_id)
        output_path = _default_output_path(clips_dir)
        stitch(clips_dir, output_path)

        scene_reports.append(
            {"scene_id": scene_id, "clip_count": len(results), "needs_review": len(needs_review), "stitched_path": str(output_path)}
        )

    print(f"\n{'#'*70}\nFULL LESSON SUMMARY\n{'#'*70}")
    for r in scene_reports:
        flag = f"  <-- {r['needs_review']} clip(s) need review" if r["needs_review"] else ""
        print(f"  Scene {r['scene_id']}: {r['clip_count']} clips -> {r['stitched_path']}{flag}")
    return scene_reports


def parse_args():
    parser = argparse.ArgumentParser(description="Generate solo clips for the 'Finding the Right Words' lesson.")
    parser.add_argument("--scene-id", type=int, default=None, help="Required for --mode preview/generate.")
    parser.add_argument(
        "--mode",
        choices=["images", "rig", "preview", "generate", "full"],
        default="preview",
        help="images: generate+cache character portraits and the background reference image (skips any already present). "
        "rig: derive+cache the per-character pose/camera/backdrop (one cheap API call, run once per scenario). "
        "preview: print prompts, free, requires a cached rig. generate: spend real Veo credits, one scene (--scene-id). "
        "full: generate+stitch every scene in the script, spends real Veo credits.",
    )
    parser.add_argument("--model-key", choices=list(VEO_MODELS), default="veo-3.1-fast")
    parser.add_argument("--only", default=None, help="Comma-separated 1-based clip indices to (re)generate, e.g. '3,6'.")
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    script = load_script()
    rig_path = rig_cache_path(OUTPUT_ROOT.parent)

    if args.mode == "images":
        if not args.api_key:
            print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
            return
        os.environ["GEMINI_API_KEY"] = args.api_key
        paths = ensure_reference_images(script, REFERENCE_IMAGES_DIR, request_id="finding_right_words")
        print(f"Reference images ready in {REFERENCE_IMAGES_DIR}:")
        print(json.dumps(paths, indent=2))
        return

    if args.mode == "rig":
        if not args.api_key:
            print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
            return
        from google import genai

        client = genai.Client(api_key=args.api_key)
        rig = generate_character_rig(client, script)
        save_rig_cache(rig_path, rig)
        print(f"Character rig saved to {rig_path}:")
        print(json.dumps(rig, indent=2))
        return

    rig = load_cached_rig(rig_path)
    if rig is None:
        print(f"ERROR: No cached character rig at {rig_path}. Run --mode rig first.")
        return

    if args.mode == "full":
        if not args.api_key:
            print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
            return
        run_full_lesson(script, args.model_key, args.api_key, rig)
        return

    if args.scene_id is None:
        print("ERROR: --scene-id is required for preview/generate.")
        return
    scene = next(s for s in script["scenes"] if s["scene_id"] == args.scene_id)

    if args.mode == "preview":
        preview(script, scene, rig)
        return

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return
    only = {int(x) for x in args.only.split(",")} if args.only else None
    generate(script, scene, args.model_key, args.api_key, rig, only=only)


if __name__ == "__main__":
    main()
