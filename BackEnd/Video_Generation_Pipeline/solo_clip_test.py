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
# Per-character pose/camera/backdrop is not hand-authored here - it's derived
# once per scenario by video_generator.character_rig (one cheap LLM call) and
# cached to output/<lesson>/character_rig.json, so this script works on any
# scenario.json without a human writing English descriptions for each new
# cast of characters first. --mode images (video_generator.reference_images)
# is the same idea applied to character portraits + the background
# reference image - both stages are idempotent, only spending on what's
# actually missing, so re-running either is always safe.
#
# Usage:
#   python solo_clip_test.py --mode images                    # generate+cache reference images, once per scenario
#   python solo_clip_test.py --mode rig                       # derive+cache the rig, once per scenario
#   python solo_clip_test.py --scene-id 1 --mode preview       # free, uses cached rig
#   python solo_clip_test.py --scene-id 1 --mode generate
#
import argparse
import json
import os
import sys
import time
from pathlib import Path

from director_experiment import (
    _char_lookup,
    _resolve_clip_scene,
    close_up_camera,
    interaction_isolation_instruction,
    references_interaction,
)
from video_generator.character_rig import (
    generate_character_rig,
    load_cached_rig,
    rig_cache_path,
    save_rig_cache,
)
from video_generator.reference_images import ensure_reference_images
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
REFERENCE_IMAGES_DIR = Path(__file__).resolve().parent / "reference_images"
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


def build_solo_clip_prompts(scene: dict, characters: list, visual_style: str, rig: dict) -> list:
    """One entry per dialogue line across every clip in the scene, in original
    order. Returns list of dicts: label, clip_id, speaker_id, line, prompt.

    Pose, camera, and backdrop are held fixed per-character (from `rig`,
    generated once by character_rig.generate_character_rig) rather than
    pulled from each clip's one-off character_actions text, so cuts back to
    the same character look like the same shot instead of a new composition
    each time. Only facial expression is left to vary with the line's content.
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
            interaction_flagged = references_interaction(line["line"])

            camera = (
                close_up_camera(speaker["name"], rig[speaker_id]["backdrop"])
                if interaction_flagged
                else rig[speaker_id]["camera"]
            )
            line_scene = {
                "setting": scene.get("setting", ""),
                "character_actions": rig[speaker_id]["pose"],
                "camera": camera,
                "audio": {**clip_scene["audio"], "dialogue": [line]},
            }
            # Only the speaker's own appearance is described here - the other
            # character's full physical description has no reason to be in a
            # prompt for a shot they're not supposed to appear in at all.
            prompt = build_veo_prompt(line_scene, [speaker], visual_style, is_continuation=False)
            if other_name:
                prompt = f"{prompt}\n\n{_solo_reinforcement(speaker['name'], other_name)}"

            if interaction_flagged and other_name:
                prompt = f"{prompt}\n\n{interaction_isolation_instruction(speaker['name'], other_name)}"

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
                    "interaction_flagged": interaction_flagged,
                    "prompt": prompt,
                }
            )

    return entries


def preview(scene: dict, characters: list, visual_style: str, rig: dict):
    entries = build_solo_clip_prompts(scene, characters, visual_style, rig)
    for i, e in enumerate(entries, start=1):
        guard_note = " [no-invent guard]" if e["guarded"] else ""
        guard_note += " [interaction guard]" if e["interaction_flagged"] else ""
        print(
            f"\n{'='*70}\n{i:02d}  {e['label']}  ({e['word_count']} words){guard_note}\n"
            f"    \"{e['line']}\"\n{'='*70}\n{e['prompt']}\n"
        )
    print(f"\n{len(entries)} solo clips would be generated, {FIRST_CLIP_SECONDS}s each.")


def generate(scene: dict, characters: list, visual_style: str, model_key: str, api_key: str, rig: dict, only=None):
    from google import genai

    client = genai.Client(api_key=api_key)
    all_entries = build_solo_clip_prompts(scene, characters, visual_style, rig)
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
    return results


def run_full_lesson(scenario: dict, characters: list, visual_style: str, model_key: str, api_key: str, rig: dict):
    """The Option B orchestrator: generate + stitch every scene in the
    scenario in one pass, instead of invoking --scene-id by hand per scene.
    Each scene gets its own stitched output file (scenes are branch points
    in an interactive lesson, not a linear sequence to concatenate into one
    video)."""
    from stitch_solo_clips import _default_output_path, stitch

    scenes = scenario["scenes"]
    print(f"\n{'#'*70}\nFULL LESSON: {len(scenes)} scenes\n{'#'*70}")

    scene_reports = []
    for scene in scenes:
        scene_id = scene["scene_id"]
        print(f"\n{'='*70}\nSCENE {scene_id}\n{'='*70}")
        results = generate(scene, characters, visual_style, model_key, api_key, rig)
        needs_review = [r for r in results if r["status"] not in ("PASS",)]

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
    parser = argparse.ArgumentParser(description="Generate solo (single-character) clips, one per dialogue line, for manual stitching.")
    parser.add_argument("--scenario", default="scenario.json")
    parser.add_argument("--scene-id", type=int, default=None, help="Required for --mode preview/generate.")
    parser.add_argument(
        "--mode",
        choices=["images", "rig", "preview", "generate", "full"],
        default="preview",
        help="images: generate+cache character portraits and the background reference image (skips any already present). "
        "rig: derive+cache the per-character pose/camera/backdrop (one cheap API call, run once per scenario). "
        "preview: print prompts, free, requires a cached rig. generate: spend real Veo credits, one scene (--scene-id). "
        "full: generate+stitch every scene in the scenario, spends real Veo credits.",
    )
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
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    rig_path = rig_cache_path(OUTPUT_ROOT.parent)

    if args.mode == "images":
        if not args.api_key:
            print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
            return
        os.environ["GEMINI_API_KEY"] = args.api_key
        paths = ensure_reference_images(scenario, REFERENCE_IMAGES_DIR, request_id="what_do_you_say_next")
        print(f"Reference images ready in {REFERENCE_IMAGES_DIR}:")
        print(json.dumps(paths, indent=2))
        return

    if args.mode == "rig":
        if not args.api_key:
            print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
            return
        from google import genai

        client = genai.Client(api_key=args.api_key)
        rig = generate_character_rig(client, scenario)
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
        run_full_lesson(scenario, characters, visual_style, args.model_key, args.api_key, rig)
        return

    if args.scene_id is None:
        print("ERROR: --scene-id is required for preview/generate.")
        return
    scene = next(s for s in scenario["scenes"] if s["scene_id"] == args.scene_id)

    if args.mode == "preview":
        preview(scene, characters, visual_style, rig)
        return

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return
    only = {int(x) for x in args.only.split(",")} if args.only else None
    generate(scene, characters, visual_style, args.model_key, args.api_key, rig, only=only)


if __name__ == "__main__":
    main()
