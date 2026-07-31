# director_experiment.py
#
# Tests whether specific "director trick" prompt/framing variants reduce the
# wrong-character-is-talking artifact, using the existing transcript_eval
# speaker-attribution judge as an objective pass/fail signal instead of manual
# review.
#
# Two buckets of test clips, pulled directly from scenario.json:
#
#   Bucket A - a single speaker, with a second character passively visible in
#   the same two-shot. Tests whether the PASSIVE character's mouth spuriously
#   moves even though only one person has any dialogue.
#
#   Bucket B - a clip whose dialogue alternates between two characters within
#   one continuous Veo generation call. Veo cannot literally execute a
#   mid-clip camera cut, so this bucket tests whether the wrong-speaker
#   artifact comes from asking one continuous shot to carry a turn change.
#
# Every test clip is generated as an isolated, reference-image-primed first
# clip (never as an extension) so the framing/attribution variable is
# isolated from the separate concern of extension-chain drift.
#
# Usage:
#   python director_experiment.py                      # preview only, no API calls
#   python director_experiment.py --mode generate       # spends real Veo credits
#   python director_experiment.py --mode generate --model-key veo-3.1-lite
#
import argparse
import itertools
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

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

EXPERIMENT_DIR = Path(__file__).resolve().parent / "output" / "director_experiment"
EXPERIMENT_LOG = EXPERIMENT_DIR / "experiment_log.json"
FIRST_CLIP_SECONDS = 8

SILENT_PARTNER_INSTRUCTION = (
    "Each character's lips move only while delivering their own numbered line "
    "above. During any other character's line, every other character keeps "
    "their mouth fully closed and still, with no visible mouth or jaw movement."
)

# Dialogue whose *words* describe a physical gesture or interaction (nodding,
# pointing, "show me", referencing the other person's posture) empirically
# bleeds the other, off-frame character into solo clips at a much higher rate
# than purely verbal lines - the semantic content itself seems to pull Veo
# toward two-shot framing even when camera/backdrop instructions say
# otherwise. Detected via keyword match so the extra guard only fires on the
# lines that actually carry that risk, not on every line.
INTERACTION_KEYWORDS = [
    "nod", "shake your head", "shake his head", "shake her head", "shook",
    "show me", "show him", "show her", "point", "pointing", "pointed",
    "crossed your arms", "crossed his arms", "crossed her arms",
    "crossed arms", "your arms", "gesture", "wave", "look at me",
    "looking at", "touch", "thumbs up", "thumbs-up", "raise your hand",
    "raised his hand", "raised her hand",
]


def references_interaction(line_text: str) -> bool:
    lower = line_text.lower()
    return any(kw in lower for kw in INTERACTION_KEYWORDS)


def interaction_isolation_instruction(speaker_name: str, other_name: str) -> str:
    return (
        f"This line's words describe a physical action or gesture (e.g. "
        f"nodding, shaking the head, pointing, showing something) - but that "
        f"description is about something {other_name} might do, NOT something "
        f"to depict in this shot. This clip shows ONLY {speaker_name} speaking "
        f"these words. Do not attempt to illustrate, depict, or hint at the "
        f"described gesture actually happening - not by {speaker_name}, and "
        f"absolutely not by cutting to or including {other_name}. Keep the "
        f"frame exactly as specified above: {speaker_name} alone, in their "
        f"fixed pose, talking."
    )


def close_up_camera(speaker_name: str, backdrop_text: str) -> dict:
    """A physically tighter framing than the usual medium/waist-up shot, for
    interaction-flagged lines. The isolation *instruction* alone hasn't
    reliably stopped the other character from bleeding into frame on lines
    whose words describe a gesture/interaction - this is a geometric
    mitigation instead: crop tight enough that there is no room in frame for
    a second person regardless of what the model wants to depict."""
    return {
        "angle": (
            f"Extreme close-up on {speaker_name}'s face and shoulders only - "
            "tightly framed, filling most of the frame. Cropped tight enough "
            "that there is no physical room in frame for anyone else to "
            f"appear, even partially, even at the frame edge. {backdrop_text}"
        ),
        "movement": "Static.",
        "lens_effect": "Shallow depth of field, background softly blurred, neutral warm tone.",
    }


TEST_CASES = [
    {"bucket": "A", "scene_id": 1, "clip_id": 1, "label": "scene1_clip1_maya_solo"},
    {"bucket": "A", "scene_id": 3, "clip_id": 2, "label": "scene3_clip2_carl_solo"},
    {"bucket": "B", "scene_id": 1, "clip_id": 2, "label": "scene1_clip2_carl_then_maya"},
    {"bucket": "B", "scene_id": 1, "clip_id": 3, "label": "scene1_clip3_carl_maya_carl"},
    {"bucket": "B", "scene_id": 2, "clip_id": 1, "label": "scene2_clip1_maya_then_carl"},
]


def _resolve_clip_scene(scene: dict, clip: dict) -> dict:
    """Mirror build_clip_prompts' per-clip field resolution (clip override,
    falling back to scene-level value), kept separate from prompt_builder
    because this experiment always treats every test clip as an isolated
    first clip (is_continuation=False), never as a mid-scene extension."""
    shared_audio = scene.get("audio", {})
    return {
        "setting": clip.get("setting", scene.get("setting", "")),
        "character_actions": clip.get(
            "character_actions", scene.get("character_actions", "")
        ),
        "camera": clip.get("camera") or scene.get("camera", {}),
        "audio": {
            "dialogue": clip.get("dialogue", []),
            "sound_effects": clip.get(
                "sound_effects", shared_audio.get("sound_effects", "none")
            ),
            "ambience": clip.get("ambience", shared_audio.get("ambience", "none")),
        },
    }


def _char_lookup(characters: list) -> dict:
    return {c["character_id"]: c for c in characters}


def _group_by_speaker(dialogue: list) -> list:
    """Collapse consecutive same-speaker lines into runs, preserving order."""
    return [
        (speaker_id, list(lines))
        for speaker_id, lines in itertools.groupby(
            dialogue, key=lambda d: d["character_id"]
        )
    ]


def _singles_camera(speaker_name: str, other_name: str) -> dict:
    return {
        "angle": (
            f"Tight single shot / over-the-shoulder favoring {speaker_name}. "
            f"{other_name} is out of frame or only a small, softly out-of-focus "
            "silhouette at the frame edge - not clearly visible."
        ),
        "movement": "Static.",
        "lens_effect": (
            "Shallow depth of field; anything behind the framed speaker is soft "
            "and out of focus."
        ),
    }


def _framing_reinforcement(other_name: str) -> str:
    """The scene's character_actions text may still describe the backgrounded
    character's visible reaction (e.g. a glance, a folded-arms posture) -
    without this, that text contradicts the singles-framing camera
    instruction telling Veo to keep them out of frame."""
    return (
        f"Any actions described above for {other_name} happen off-frame or as a "
        f"soft, out-of-focus silhouette, consistent with the camera framing - "
        f"{other_name} does not occupy meaningful frame space or draw visual attention."
    )


def variant_v0_baseline(clip_scene, characters, visual_style):
    prompt = build_veo_prompt(clip_scene, characters, visual_style, is_continuation=False)
    return [(clip_scene["audio"]["dialogue"], prompt)]


def variant_v1_silent_partner(clip_scene, characters, visual_style):
    base = build_veo_prompt(clip_scene, characters, visual_style, is_continuation=False)
    prompt = f"{base}\n\n{SILENT_PARTNER_INSTRUCTION}"
    return [(clip_scene["audio"]["dialogue"], prompt)]


def variant_v2_singles_framing(clip_scene, characters, visual_style):
    """Bucket A only - the clip has exactly one speaker, so a single
    unambiguous framing (favoring that speaker, backgrounding the other
    character) can hold for the clip's entire duration."""
    dialogue = clip_scene["audio"]["dialogue"]
    speaker_ids = {d["character_id"] for d in dialogue}
    if len(speaker_ids) != 1:
        raise ValueError("variant_v2_singles_framing only applies to single-speaker clips")

    lookup = _char_lookup(characters)
    speaker_id = next(iter(speaker_ids))
    speaker = lookup[speaker_id]
    others = [c for c in characters if c["character_id"] != speaker_id]
    other_name = others[0]["name"] if others else ""

    scene_with_camera = {**clip_scene, "camera": _singles_camera(speaker["name"], other_name)}
    prompt = build_veo_prompt(scene_with_camera, characters, visual_style, is_continuation=False)
    if other_name:
        prompt = f"{prompt}\n\n{_framing_reinforcement(other_name)}"
    return [(dialogue, prompt)]


def variant_v3_one_speaker_per_clip(clip_scene, characters, visual_style):
    """Bucket B only - splits a multi-turn clip into one real sub-clip per
    speaker run, each its own generation call (a real cut), instead of asking
    one continuous shot to fake a cut via camera text."""
    lookup = _char_lookup(characters)
    dialogue = clip_scene["audio"]["dialogue"]
    results = []
    for speaker_id, lines in _group_by_speaker(dialogue):
        speaker = lookup[speaker_id]
        others = [c for c in characters if c["character_id"] != speaker_id]
        other_name = others[0]["name"] if others else ""
        sub_scene = {
            **clip_scene,
            "camera": _singles_camera(speaker["name"], other_name),
            "audio": {**clip_scene["audio"], "dialogue": lines},
        }
        prompt = build_veo_prompt(sub_scene, characters, visual_style, is_continuation=False)
        if other_name:
            prompt = f"{prompt}\n\n{_framing_reinforcement(other_name)}"
        results.append((lines, prompt))
    return results


BUCKET_VARIANTS = {
    "A": [
        ("v0_baseline", variant_v0_baseline),
        ("v1_silent_partner", variant_v1_silent_partner),
        ("v2_singles_framing", variant_v2_singles_framing),
    ],
    "B": [
        ("v0_baseline", variant_v0_baseline),
        ("v1_silent_partner", variant_v1_silent_partner),
        ("v3_one_speaker_per_clip", variant_v3_one_speaker_per_clip),
    ],
}


def _load_experiment_log() -> list:
    if EXPERIMENT_LOG.exists():
        with open(EXPERIMENT_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_experiment_log(entries: list):
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    with open(EXPERIMENT_LOG, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def preview(scenario: dict, cases: list):
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scene_lookup = {s["scene_id"]: s for s in scenario["scenes"]}

    for case in cases:
        scene = scene_lookup[case["scene_id"]]
        clip = next(c for c in scene["clips"] if c["clip_id"] == case["clip_id"])
        clip_scene = _resolve_clip_scene(scene, clip)

        print(f"\n{'#'*70}\nCASE {case['label']}  (bucket {case['bucket']})\n{'#'*70}")
        for variant_name, variant_fn in BUCKET_VARIANTS[case["bucket"]]:
            sub_prompts = variant_fn(clip_scene, characters, visual_style)
            for i, (dialogue, prompt) in enumerate(sub_prompts):
                speakers = [d["character_id"] for d in dialogue]
                print(
                    f"\n{'='*70}\n{variant_name}  sub-clip {i}  speakers={speakers}\n{'='*70}\n{prompt}\n"
                )


def generate(scenario: dict, cases: list, model_key: str, api_key: str, variants=None, repeat=1):
    from google import genai

    client = genai.Client(api_key=api_key)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scene_lookup = {s["scene_id"]: s for s in scenario["scenes"]}
    model_api_name = VEO_MODELS[model_key]
    reference_images = REFERENCE_IMAGES or None

    entries = _load_experiment_log()
    results_summary = []

    for case in cases:
        scene = scene_lookup[case["scene_id"]]
        clip = next(c for c in scene["clips"] if c["clip_id"] == case["clip_id"])
        clip_scene = _resolve_clip_scene(scene, clip)

        bucket_variants = BUCKET_VARIANTS[case["bucket"]]
        if variants:
            bucket_variants = [
                (name, fn) for name, fn in bucket_variants if name in variants
            ]

        for variant_name, variant_fn in bucket_variants:
            sub_prompts = variant_fn(clip_scene, characters, visual_style)
            for sub_idx, (dialogue, prompt) in enumerate(sub_prompts):
                for rep in range(repeat):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    label = f"{case['label']}__{variant_name}__sub{sub_idx}_rep{rep}_{ts}"
                    video_path = str(EXPERIMENT_DIR / f"{label}.mp4")
                    print(f"\n{'-'*70}\n{label}\n{'-'*70}")

                    start = time.time()
                    error = None
                    report = None
                    try:
                        video_obj, attempts = generate_first_clip(
                            client,
                            prompt,
                            reference_images=reference_images,
                            duration_seconds=FIRST_CLIP_SECONDS,
                            model=model_api_name,
                        )
                        EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
                        download_video(client, video_obj, video_path)
                        report = evaluate_clip(
                            client=client,
                            video_path=video_path,
                            scene_id=case["scene_id"],
                            clip_id=f"{case['clip_id']}_{variant_name}_{sub_idx}_{rep}",
                            dialogue=dialogue,
                            characters=characters,
                        )
                    except Exception as e:
                        error = str(e)
                        print(f"  ERROR: {error}")

                    wall_time = time.time() - start
                    cost = estimate_cost(model_key, RESOLUTION, FIRST_CLIP_SECONDS)
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "bucket": case["bucket"],
                        "case_label": case["label"],
                        "scene_id": case["scene_id"],
                        "clip_id": case["clip_id"],
                        "variant": variant_name,
                        "sub_clip_index": sub_idx,
                        "repeat_index": rep,
                        "expected_speakers": [d["character_id"] for d in dialogue],
                        "model_key": model_key,
                        # Not error is None: download can succeed (money already spent)
                        # even if the later eval step throws - don't orphan that file.
                        "video_path": video_path if Path(video_path).exists() else None,
                        "generation_time": round(wall_time, 1),
                        "estimated_cost_usd": cost,
                        "error": error,
                        "dialogue_match_passed": (
                            report["dialogue_match"]["passed"] if report else None
                        ),
                        "attribution_passed": (
                            report["speaker_attribution"]["attribution_passed"]
                            if report and report["speaker_attribution"]
                            else None
                        ),
                        "eval_report_path": (
                            str(Path(video_path).with_suffix("")) + "_eval.json"
                            if report
                            else None
                        ),
                    }
                    entries.append(entry)
                    _save_experiment_log(entries)
                    results_summary.append(entry)

                    status = (
                        "PASS" if entry["attribution_passed"]
                        else "FAIL" if entry["attribution_passed"] is False
                        else "ERROR"
                    )
                    print(f"  {status}  (~${cost:.2f}, {wall_time:.0f}s)")

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for e in results_summary:
        status = (
            "PASS" if e["attribution_passed"]
            else "FAIL" if e["attribution_passed"] is False
            else "ERROR"
        )
        print(
            f"  [{status:5s}] {e['case_label']:35s} {e['variant']:25s} "
            f"sub{e['sub_clip_index']} rep{e.get('repeat_index', 0)}"
        )
    total_cost = sum(e["estimated_cost_usd"] or 0 for e in results_summary)
    print(f"\nTotal estimated cost this run: ${total_cost:.2f}")
    print(f"Full log: {EXPERIMENT_LOG}")


def parse_args():
    parser = argparse.ArgumentParser(description="Test director tricks against speaker-attribution accuracy.")
    parser.add_argument("--mode", choices=["preview", "generate"], default="preview")
    parser.add_argument("--model-key", choices=list(VEO_MODELS), default="veo-3.1-lite")
    parser.add_argument(
        "--cases",
        default=None,
        help="Comma-separated case labels to restrict to (default: all).",
    )
    parser.add_argument(
        "--variants",
        default=None,
        help="Comma-separated variant names to restrict to (default: all variants for each case's bucket).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of independent samples to generate per case/variant/sub-clip (default: 1).",
    )
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    scenario = load_scenario("scenario.json")
    cases = TEST_CASES
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["label"] in wanted]

    if args.mode == "preview":
        preview(scenario, cases)
        return

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return
    variants = set(args.variants.split(",")) if args.variants else None
    generate(scenario, cases, args.model_key, args.api_key, variants=variants, repeat=args.repeat)


if __name__ == "__main__":
    main()
