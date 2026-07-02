import argparse
import os
from pathlib import Path

from .logging_utils import OUTPUT_DIR, LOG_FILE
from .prompt_builder import build_clip_prompts
from .scenario_loader import load_scenario
from .veo_api import REFERENCE_IMAGES
from .pipeline import run_scenario_pipeline


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
    parser = argparse.ArgumentParser(description="Generate scenario videos using Veo.")
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
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key (or set GEMINI_API_KEY env var).",
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
    return parser.parse_args()


def main():
    load_env()
    args = parse_args()

    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return

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

    init_output_dir()
    from google import genai

    client = genai.Client(api_key=args.api_key)

    filtered_scenario = {**scenario, "scenes": scenes}
    results = run_scenario_pipeline(
        client=client,
        scenario=filtered_scenario,
        reference_images=REFERENCE_IMAGES or None,
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
