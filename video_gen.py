"""
Video Generation
Generates videos from JSON using different Veo models.
This is for testing generation of one scene for model comparison. This also logss results.
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

#load env
from pathlib import Path

def load_env():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

load_env()

#models
VEO_MODELS = {
    "veo-3.1": "veo-3.1-generate-preview",
    "veo-3.1-fast": "veo-3.1-fast-generate-preview",
    "veo-3.1-lite": "veo-3.1-lite-generate-preview",
    "veo-2": "veo-2.0-generate-001",
}

#defaults
DEFAULT_MODEL = "veo-3.1"
DEFAULT_RESOLUTION = "720p" #cheap for testing
DEFAULT_ASPECT = "16:9"
OUTPUT_DIR = Path("output")
LOG_FILE = OUTPUT_DIR / "generation_log.json"


#PROMPT

def build_veo_prompt(scene: dict, characters: list, visual_style: str, is_continuation: bool = False) -> str:
    """
    Converts scene, character descriptions, and visual style from JSON into a prompt for Veo.

    is_continuation: set True for extension clips to anchor visual continuity explicitly.
    """

    #character block
    char_lookup = {c["character_id"]: c for c in characters}
    char_lines = []
    for cid, char in char_lookup.items():
        a = char["appearance"]
        char_lines.append(
            f"{char['name']} ({char['role']}): "
            f"{a['skin_tone']} skin, {a['hair']}, {a['uniform']}. "
            f"Emotional tone: {char['emotional_baseline']}."
        )
    character_block = " | ".join(char_lines)

    #dialogue block — numbered list with explicit speaker-order lock to prevent Veo from swapping voices
    dialogue_entries = scene.get("audio", {}).get("dialogue", [])
    dialogue_lines = []
    for idx, line in enumerate(dialogue_entries, start=1):
        char = char_lookup.get(line["character_id"])
        name = char["name"] if char else line["character_id"]
        dialogue_lines.append(f'{idx}. {name}: "{line["line"]}"')

    if dialogue_lines:
        dialogue_block = (
            "Spoken in this exact order — each character delivers only their own numbered line:\n    "
            + "\n    ".join(dialogue_lines)
            + "\n    Do not swap, merge, or reorder lines between characters."
        )
    else:
        #Problem 6: explicitly suppress speech when a clip has no dialogue, so Veo does not invent lines
        dialogue_block = "None — no spoken words in this clip. All characters act and react silently."

    #camera block
    cam = scene.get("camera", {})
    camera_block = (
        f"{cam.get('angle', '')}. "
        f"{cam.get('movement', '')}. "
        f"{cam.get('lens_effect', '')}."
    )

    #sound block
    audio = scene.get("audio", {})
    sound_block = (
        f"Sound effects: {audio.get('sound_effects', 'none')}. "
        f"Ambience: {audio.get('ambience', 'none')}."
    )

    #full prompt
    prompt = f"""Visual style: {visual_style}
    
    Characters: {character_block}
    
    Setting: {scene.get('setting', '')}
    
    Character actions: {scene.get('character_actions', '')}
    
    Camera: {camera_block}
    
    Dialogue: {dialogue_block}
    
    Audio: {sound_block}"""

    #on-screen text if present
    if scene.get("on_screen_text"):
        prompt += f"\n\nOn-screen text overlay at end: \"{scene['on_screen_text']}\""

    #character consistency block — built dynamically from JSON, not hardcoded to any specific character
    consistency_lines = []
    for char in characters:
        a = char["appearance"]
        consistency_lines.append(
            f"{char['name']} always wears {a['uniform']}; "
            f"{a['skin_tone']} skin, {a['hair']}. "
            f"Do not change {char['name']}'s clothing, hair, skin tone, or facial features at any point."
        )
    prompt += (
        "\n\nCharacter reference images are provided. "
        + " ".join(consistency_lines)
        + " Do not introduce any additional characters into frame."
    )

    #continuation anchor — extension clips must not visually reset anything established in the prior clip
    if is_continuation:
        prompt += (
            "\n\nThis clip is a direct continuation of the previous clip. "
            "All visual elements — character appearances, clothing, lighting, room layout, and environment — "
            "must remain exactly as established in the prior clip. Do not reset, alter, or reintroduce any visual element."
        )

    #text overlay instruction — allow on_screen_text only where explicitly specified, suppress everything else
    if scene.get("on_screen_text"):
        prompt += "\n\nDo not include any other text overlays, captions, or subtitles beyond the specified on-screen text at the end."
    else:
        prompt += "\n\nDo not include any text overlays, captions, subtitles, or on-screen text in the video."
    
    return prompt.strip()


def load_scenario(json_path: str) -> dict:
    """Load and validate the scenario JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    required = ["scenes", "characters", "visual_style"]
    for key in required:
        if key not in scenario:
            raise ValueError(f"Scenario JSON missing required key: '{key}'")
    return scenario


#LOG RESULTS

def init_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)

def load_log() -> list:
    """Load existing generation log or return empty list."""
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_log(entries: list):
    """Save generation log"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

def log_generation(
    scene_id: int,
    model_key: str,
    prompt: str,
    output_file: str,
    duration_seconds: float,
    success: bool,
    error: str = None,
):
    """
    Add a generation result to the log file. Each entry has info needed to reproduce or review the generation.
    """
    entries = load_log()
    entry = {
        "timestamp":       datetime.now().isoformat(),
        "scene_id":        scene_id,
        "model":           model_key,
        "model_api_name":  VEO_MODELS.get(model_key, model_key),
        "prompt":          prompt,
        "output_file":     output_file,
        "generation_time": round(duration_seconds, 1),
        "success":         success,
        "error":           error,
    }
    entries.append(entry)
    save_log(entries)
    return entry

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

    # Load video
    video = VideoFileClip(video_path)
    duration = video.duration
    char_lookup = {c["character_id"]: c["name"] for c in characters}

    # Distribute dialogue evenly across video duration
    # Reserve last 2 seconds for on_screen_text if present
    dialogue_duration = duration - 2 if on_screen_text else duration
    clip_duration = dialogue_duration / max(len(dialogue), 1)

    caption_clips = []

    for i, line in enumerate(dialogue):
         # Skip non-dialogue entries
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

    # Add on-screen text end card if present
    if on_screen_text:
        # Dark background strip
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

    # Composite and export
    final = CompositeVideoClip([video] + caption_clips)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)

    print(f"✓ Captioned video saved: {output_path}")
    video.close()
    final.close()
    return output_path


#VIDEO GENERATION

def generate_video(
    client,
    prompt: str,
    scene_id: int,
    model_key: str = DEFAULT_MODEL,
    resolution: str = DEFAULT_RESOLUTION,
    aspect_ratio: str = DEFAULT_ASPECT,
    prompt_override: str = None,
    reference_images: list = None,
    poll_interval: int = 10,
) -> dict:
    """
    Generate a single video from a prompt using Veo.
    Returns a log entry dict with results.

    Args:
        client:          Initialized Gemini client
        prompt:          Auto-built prompt from build_veo_prompt()
        scene_id:        Scene number from the scenario JSON
        model_key:       Short model name e.g. 'veo-3.1' or 'veo-2'
        resolution:      '720p', '1080p', or '4k'
        aspect_ratio:    '16:9' or '9:16'
        prompt_override: If provided, uses this instead of the auto-built prompt
        poll_interval:   Seconds between polling for completion
    """
    from google.genai import types

    # Use override prompt if provided
    final_prompt = prompt_override if prompt_override else prompt

    model_api_name = VEO_MODELS.get(model_key)
    if not model_api_name:
        raise ValueError(f"Unknown model key '{model_key}'. Choose from: {list(VEO_MODELS.keys())}")

    # Output filename includes scene + model + timestamp for easy comparison
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = str(OUTPUT_DIR / f"scene{scene_id}_{model_key}_{timestamp}.mp4")

    print(f"\n{'─'*60}")
    print(f"  Scene:      {scene_id}")
    print(f"  Model:      {model_key} ({model_api_name})")
    print(f"  Resolution: {resolution}  |  Aspect: {aspect_ratio}")
    print(f"  Output:     {output_file}")
    print(f"{'─'*60}")
    print(f"\nPrompt preview (first 300 chars):\n{final_prompt[:300]}...\n")

    start_time = time.time()

    try:
        # Submit generation request
        print("Submitting to Veo API...")
        # Build reference images config if provided
        ref_image_configs = []
        if reference_images:
            from google.genai.types import VideoGenerationReferenceImage, Image as GenaImage
            for img_path in reference_images:
                with open(img_path, "rb") as f:
                    image_bytes = f.read()
                ref_image_configs.append(
                    VideoGenerationReferenceImage(
                        image=GenaImage(
                            image_bytes=image_bytes,
                            mime_type="image/png",
                        ),
                        reference_type="asset",
                    )
                )

        operation = client.models.generate_videos(
            model=model_api_name,
            prompt=final_prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                number_of_videos=1,
                reference_images=ref_image_configs if ref_image_configs else None,
            ),
        )

        # Poll until complete
        print("Waiting for generation to complete ", end="", flush=True)
        while not operation.done:
            time.sleep(poll_interval)
            operation = client.operations.get(operation)
            print(".", end="", flush=True)
        print(" done!")

        # Extract and save video
        generated_videos = operation.response.generated_videos
        if not generated_videos:
            raise RuntimeError("Veo returned no videos — check your API quota and prompt.")

        video_uri = generated_videos[0].video.uri
        video_data = client.files.download(file=video_uri)
        with open(output_file, "wb") as f:
            f.write(video_data)

        duration = time.time() - start_time
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"✓ Saved: {output_file} ({size_mb:.1f} MB) in {duration:.0f}s")

        return log_generation(
            scene_id=scene_id,
            model_key=model_key,
            prompt=final_prompt,
            output_file=output_file,
            duration_seconds=duration,
            success=True,
        )

    except Exception as e:
        duration = time.time() - start_time
        print(f"✗ Generation failed: {e}")
        return log_generation(
            scene_id=scene_id,
            model_key=model_key,
            prompt=final_prompt,
            output_file=output_file,
            duration_seconds=duration,
            success=False,
            error=str(e),
        )
    
#CLI STUFF

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate nursing scenario videos using Veo."
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
        default=DEFAULT_MODEL,
        choices=list(VEO_MODELS.keys()),
        help=f"Veo model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--compare-models",
        action="store_true",
        help="Run the same scene through all Veo models for comparison.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key (or set GEMINI_API_KEY env var).",
    )
    parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        choices=["720p", "1080p", "4k"],
        help=f"Output resolution (default: {DEFAULT_RESOLUTION}).",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=DEFAULT_ASPECT,
        choices=["16:9", "9:16"],
        help=f"Aspect ratio (default: {DEFAULT_ASPECT}).",
    )
    parser.add_argument(
        "--prompt-override",
        default=None,
        help="Skip auto-built prompt and use this string instead.",
    )
    parser.add_argument(
        "--reference-images",
        nargs="+",
        default=None,
        help="Paths to up to 3 reference images for character consistency.",
    )
    parser.add_argument(
        "--preview-prompt",
        action="store_true",
        help="Print the generated Veo prompt without generating a video.",
    )

    parser.add_argument(
        "--add-captions",
        action="store_true",
        help="Burn dialogue captions onto the generated video after generation.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    #Valid API key
    if not args.api_key:
        print("ERROR: No Gemini API key. Use --api-key or set GEMINI_API_KEY.")
        return

    #Load scenario
    scenario = load_scenario(args.scenario)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scenes = scenario["scenes"]

    #Filter to specific scene if requested
    if args.scene_id is not None:
        scenes = [s for s in scenes if s["scene_id"] == args.scene_id]
        if not scenes:
            print(f"ERROR: No scene found with id {args.scene_id}")
            return

    #Look at prompt only — no generation
    if args.preview_prompt:
        for scene in scenes:
            prompt = build_veo_prompt(scene, characters, visual_style)
            print(f"\n{'─'*60}")
            print(f"Scene {scene['scene_id']} prompt:\n")
            print(prompt)
        return

    #Init output directory and Gemini client
    init_output_dir()
    from google import genai
    client = genai.Client(api_key=args.api_key)

    #Determine which models to run
    models_to_run = list(VEO_MODELS.keys()) if args.compare_models else [args.model]

    #Generate
    results = []
    for scene in scenes:
        prompt = build_veo_prompt(scene, characters, visual_style)
        for model_key in models_to_run:
            result = generate_video(
                client=client,
                prompt=prompt,
                scene_id=scene["scene_id"],
                model_key=model_key,
                resolution=args.resolution,
                aspect_ratio=args.aspect_ratio,
                prompt_override=args.prompt_override,
                reference_images=args.reference_images,
            )
            results.append(result)

            
            # Burn captions if requested and generation succeeded
            if args.add_captions and result["success"]:
                burn_captions(
                    video_path=result["output_file"],
                    dialogue=scene.get("audio", {}).get("dialogue", []),
                    characters=characters,
                    on_screen_text=scene.get("on_screen_text"),
                )

    #Summary
    print(f"\n{'─'*60}")
    print(f"GENERATION SUMMARY")
    print(f"{'─'*60}")
    succeeded = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    print(f"✓ Succeeded: {len(succeeded)}")
    print(f"✗ Failed:    {len(failed)}")
    for r in succeeded:
        print(f"  scene{r['scene_id']} | {r['model']} | {r['generation_time']}s | {r['output_file']}")
    for r in failed:
        print(f"  scene{r['scene_id']} | {r['model']} | ERROR: {r['error']}")
    print(f"\nFull log: {LOG_FILE}")


if __name__ == "__main__":
    main()