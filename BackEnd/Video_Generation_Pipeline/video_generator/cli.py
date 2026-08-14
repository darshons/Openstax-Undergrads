import argparse
import os
from pathlib import Path

from .logging_utils import OUTPUT_DIR, LOG_FILE
from .prompt_builder import build_clip_prompts
from .scenario_loader import load_scenario

# NOTE: veo modules (and google.genai) are imported lazily inside main() —
# the default local ComfyUI path must work with no Gemini dependencies or
# GEMINI_API_KEY present at all.


def load_env():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def init_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)


def burn_captions(
    video_path: str,
    dialogue: list,
    characters: list,
    on_screen_text: str = None,
    output_path: str = None,
) -> str:
    from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip

    if not output_path:
        base = video_path.replace(".mp4", "")
        output_path = f"{base}_captioned.mp4"

    print(f"\nBurning captions onto: {video_path}")

    video = VideoFileClip(video_path)
    duration = video.duration
    char_lookup = {c["character_id"]: c["name"] for c in characters}

    dialogue_duration = duration - 2 if on_screen_text else duration
    clip_duration = dialogue_duration / max(len(dialogue), 1)

    caption_clips = []

    for i, line in enumerate(dialogue):
        if not line.get("character_id"):
            continue
        name = char_lookup.get(line["character_id"], line["character_id"])
        text = f"{name}: {line['line']}"
        start = i * clip_duration
        end = min(start + clip_duration, dialogue_duration)

        caption = (
            TextClip(
                text=text,
                font_size=22,
                color="white",
                stroke_color="black",
                stroke_width=1.5,
                method="caption",
                size=(video.w - 80, None),
            )
            .with_start(start)
            .with_end(end)
            .with_position(("center", video.h - 80))
        )
        caption_clips.append(caption)

    if on_screen_text:
        bg = (
            ColorClip(size=(video.w, 60), color=(0, 0, 0))
            .with_opacity(0.7)
            .with_start(duration - 2)
            .with_end(duration)
            .with_position(("center", video.h - 90))
        )
        end_text = (
            TextClip(
                text=on_screen_text,
                font_size=18,
                color="white",
                method="caption",
                size=(video.w - 80, None),
            )
            .with_start(duration - 2)
            .with_end(duration)
            .with_position(("center", video.h - 80))
        )
        caption_clips.extend([bg, end_text])

    final = CompositeVideoClip([video] + caption_clips)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)

    print(f"✓ Captioned video saved: {output_path}")
    video.close()
    final.close()
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate scenario videos locally via ComfyUI Wan2.2 "
        "(default) or via Google Veo (deprecated)."
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Path to your scenario JSON file.",
    )
    parser.add_argument(
        "--scene-id",
        type=int,
        default=None,
        help="Scene ID to generate. Omit to generate all scenes.",
    )
    parser.add_argument(
        "--model",
        default="local",
        choices=["local", "veo-3.1", "veo-3.1-fast", "veo-3.1-lite", "veo-2"],
        help="Video backend. 'local' (default) = ComfyUI Wan2.2 on this "
        "machine, no API key needed. veo-* backends are DEPRECATED and "
        "require GEMINI_API_KEY.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="(local only) Build and print the exact ComfyUI /prompt JSON "
        "payload for each clip, validate the node graph and model files, "
        "and exit without submitting any job.",
    )
    parser.add_argument(
        "--i2v-start-image",
        default=None,
        help="(local only) Path to a start image; switches the local backend "
        "from T2V to I2V. Later clips chain from the previous clip's last frame.",
    )
    parser.add_argument(
        "--character-lora",
        default=None,
        help="(local only) LoRA filename in ComfyUI models/loras applied to "
        "the low-noise branch (e.g. mayanurse_low.safetensors).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="(local only) Sampler noise seed (default: 30003).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="[DEPRECATED, veo-* only] Gemini API key (or set GEMINI_API_KEY env var).",
    )
    parser.add_argument(
        "--preview-prompt",
        action="store_true",
        help="Print the generated Veo prompts (one per clip) without generating a video.",
    )
    parser.add_argument(
        "--add-captions",
        action="store_true",
        help="Burn dialogue captions onto the generated video after generation.",
    )
    parser.add_argument(
        "--verify-clips",
        action="store_true",
        help="Transcribe and evaluate each clip against the script as it's generated "
        "(via Transcript_Eval_Pipeline), regenerating on failure. Adds a Gemini vision "
        "judge call and a cumulative-video download per clip — real extra cost/latency.",
    )
    parser.add_argument(
        "--eval-retries",
        type=int,
        default=1,
        help="Max regeneration attempts for a clip that fails --verify-clips eval (default: 1).",
    )
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    scenario = load_scenario(args.scenario)
    characters = scenario["characters"]
    scenes = scenario["scenes"]

    if args.scene_id is not None:
        scenes = [s for s in scenes if s["scene_id"] == args.scene_id]
        if not scenes:
            print(f"ERROR: No scene found with id {args.scene_id}")
            return

    if args.preview_prompt:
        visual_style = scenario["visual_style"]
        for scene in scenes:
            clip_prompts = build_clip_prompts(scene, characters, visual_style)
            print(
                f"\n{'#'*60}\nSCENE {scene['scene_id']}  ({len(clip_prompts)} clips)\n{'#'*60}"
            )
            for i, p in enumerate(clip_prompts, start=1):
                print(f"\n{'='*60}\nCLIP {i}\n{'='*60}\n{p}\n")
        return

    filtered_scenario = {**scenario, "scenes": scenes}

    # ------------------------------------------------------------------
    # Local ComfyUI Wan2.2 backend (default) — no Gemini/Google imports,
    # no API key.
    # ------------------------------------------------------------------
    if args.model == "local":
        from . import local_api

        mode = "i2v" if args.i2v_start_image else "t2v"
        seed = args.seed if args.seed is not None else local_api.DEFAULT_SEED
        visual_style = scenario["visual_style"]

        if args.dry_run:
            for scene in scenes:
                clip_prompts = build_clip_prompts(scene, characters, visual_style)
                local_api.dry_run_scene(
                    scene["scene_id"],
                    clip_prompts,
                    mode=mode,
                    start_image=args.i2v_start_image,
                    seed=seed,
                    character_lora=args.character_lora,
                )
            return

        init_output_dir()
        results = local_api.run_scenario_pipeline_local(
            filtered_scenario,
            mode=mode,
            start_image=args.i2v_start_image,
            seed=seed,
            character_lora=args.character_lora,
        )

    # ------------------------------------------------------------------
    # DEPRECATED: Google Veo backends. Kept selectable, but everything
    # Gemini-related stays behind this branch.
    # ------------------------------------------------------------------
    else:
        print(
            f"WARNING: --model {args.model} (Google Veo) is DEPRECATED — "
            "the default local ComfyUI Wan2.2 backend replaces it."
        )
        if args.dry_run:
            print("ERROR: --dry-run is only supported with --model local.")
            return
        if not args.api_key:
            print(
                "ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY "
                "(only required for deprecated veo-* models)."
            )
            return

        from . import veo_api

        # set_model BEFORE importing pipeline: pipeline binds MODEL_KEY by
        # value at its own import time (used for logging/cost lookups).
        veo_api.set_model(args.model)
        from .pipeline import run_scenario_pipeline

        init_output_dir()
        from google import genai

        client = genai.Client(api_key=args.api_key)

        results = run_scenario_pipeline(
            client=client,
            scenario=filtered_scenario,
            reference_images=veo_api.REFERENCE_IMAGES or None,
            verify_clips=args.verify_clips,
            eval_retries=args.eval_retries,
        )

    if args.add_captions:
        for result in results:
            if result["success"]:
                scene = next(
                    (s for s in scenes if s["scene_id"] == result["scene_id"]), None
                )
                if scene:
                    all_dialogue = [
                        line
                        for clip in scene.get("clips", [])
                        for line in clip.get("dialogue", [])
                    ]
                    burn_captions(
                        video_path=result["output_file"],
                        dialogue=all_dialogue,
                        characters=characters,
                        on_screen_text=scene.get("on_screen_text"),
                    )

    print(f"\n{'─'*60}")
    print("GENERATION SUMMARY")
    print(f"{'─'*60}")
    succeeded = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    print(f"✓ Succeeded: {len(succeeded)}")
    print(f"✗ Failed:    {len(failed)}")
    for r in succeeded:
        print(f"  scene{r['scene_id']} | {r['output_file']}")
    for r in failed:
        print(f"  scene{r['scene_id']} | ERROR: {r['error']}")
    print(f"\nFull log: {LOG_FILE}")


if __name__ == "__main__":
    main()
