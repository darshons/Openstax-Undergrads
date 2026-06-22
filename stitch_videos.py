#!/usr/bin/env python3
"""
Stitch Pipeline
Generates vides by stitching Veo clips together using Veo's
video extension feature. Each clip continues from the last second
of the previous one.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from video_gen import (
    load_scenario,
    build_veo_prompt,
    init_output_dir,
    log_generation,
    VEO_MODELS,
    OUTPUT_DIR,
)

#SETTINGS
SCENARIO_FILE = "scenario.json"
MODEL = "veo-3.1-generate-preview"
RESOLUTION = "720p"
ASPECT_RATIO = "16:9"
POLL_INTERVAL = 10
REFERENCE_IMAGES = ["maya_reference.png", "carl_reference.png"]


#GENERATE FIRST CLIP
def generate_first_clip(
    client,
    prompt: str,
    scene_id: int,
    clip_index: int,
    reference_images: list = None,
) -> str:
    """
    Generates the first 8-second clip for a scene.
    Returns local path to saved video file.
    """
    from google.genai import types

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = str(OUTPUT_DIR / f"scene{scene_id}_clip{clip_index}_{timestamp}.mp4")

    print(f"\n  Generating clip {clip_index} (first clip)...")

    #build reference image configs if provided
    ref_image_configs = []
    if reference_images:
        from google.genai.types import VideoGenerationReferenceImage, Image as GenaImage
        for img_path in reference_images:
            with open(img_path, "rb") as f:
                image_bytes = f.read()
            ref_image_configs.append(
                VideoGenerationReferenceImage(
                    image=GenaImage(image_bytes=image_bytes, mime_type="image/png"),
                    reference_type="asset",
                )
            )

    operation = client.models.generate_videos(
        model=MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
            number_of_videos=1,
            reference_images=ref_image_configs if ref_image_configs else None,
        ),
    )

    operation = _poll_until_done(client, operation)
    video_obj = operation.response.generated_videos[0].video
    return _download_clip(client, operation, output_file), video_obj

#GENERATE EXTENSION CLIP
def generate_extension_clip(
    client,
    prompt: str,
    previous_video_obj,
    scene_id: int,
    clip_index: int,
) -> tuple:
    """
    Extends a previously generated Veo video by passing the video object
    directly from the previous operation response.
    Returns (local_path, video_obj) tuple.
    """
    from google.genai import types

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = str(OUTPUT_DIR / f"scene{scene_id}_clip{clip_index}_{timestamp}.mp4")

    print(f"\n  Generating clip {clip_index} (extension)...")

    operation = client.models.generate_videos(
        model=MODEL,
        prompt=prompt,
        video=previous_video_obj,
        config=types.GenerateVideosConfig(
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
            number_of_videos=1,
        ),
    )

    operation = _poll_until_done(client, operation)
    video_obj = operation.response.generated_videos[0].video
    return _download_clip(client, operation, output_file), video_obj

#POLLING
def _poll_until_done(client, operation):
    """Poll operation until Veo finishes generating."""
    print("  Waiting for generation ", end="", flush=True)
    while not operation.done:
        time.sleep(POLL_INTERVAL)
        operation = client.operations.get(operation)
        print(".", end="", flush=True)
    print(" done!")
    return operation


#DOWNLOAD CLIP
def _download_clip(client, operation, output_file: str) -> str:
    """Download generated video and save to output folder."""
    generated_videos = operation.response.generated_videos
    if not generated_videos:
        raise RuntimeError("Veo returned no videos — check quota and prompt.")

    video_uri = generated_videos[0].video.uri
    video_data = client.files.download(file=video_uri)
    with open(output_file, "wb") as f:
        f.write(video_data)

    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  Saved: {output_file} ({size_mb:.1f} MB)")
    return output_file


#STITCH CLIPS TOGETHER
def stitch_clips(clip_paths: list, output_path: str) -> str:
    """
    Concatenates a list of video clips into one final video using moviepy.
    """
    from moviepy import VideoFileClip, concatenate_videoclips

    print(f"\nStitching {len(clip_paths)} clips together...")
    clips = [VideoFileClip(p) for p in clip_paths]
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)

    for clip in clips:
        clip.close()
    final.close()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Final video saved: {output_path} ({size_mb:.1f} MB)")
    return output_path


#MAIN SCENE PIPELINE
def run_scene_pipeline(
    client,
    scene: dict,
    characters: list,
    visual_style: str,
    num_clips: int = 3,
    use_reference_images: bool = True,
):
    """
    Full pipeline for one scene:
    1. Generate first clip from prompt
    2. Upload to Files API
    3. Extend num_clips-1 more times
    4. Stitch all clips into one final video

    Args:
        num_clips: how many 8-second clips to chain (3 = ~24 seconds)
        use_reference_images: whether to pass maya/carl reference images
    """
    scene_id = scene["scene_id"]
    prompt = build_veo_prompt(scene, characters, visual_style)
    ref_images = REFERENCE_IMAGES if use_reference_images else None

    print(f"\n{'─'*60}")
    print(f"SCENE {scene_id} — generating {num_clips} clips (~{num_clips * 8}s total)")
    print(f"{'─'*60}")

    start_time = time.time()
    clip_paths = []

    #generate first clip
    first_clip, previous_video_obj = generate_first_clip(
        client, prompt, scene_id, clip_index=1, reference_images=ref_images
    )
    clip_paths.append(first_clip)

    for i in range(2, num_clips + 1):
        next_clip, previous_video_obj = generate_extension_clip(
            client, prompt, previous_video_obj, scene_id, clip_index=i
        )
        clip_paths.append(next_clip)

    #stitch all clips
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sprite_label = "sprites" if use_reference_images else "no_sprites"
    final_path = str(OUTPUT_DIR / f"scene{scene_id}_final_{sprite_label}_{timestamp}.mp4")
    stitch_clips(clip_paths, final_path)

    total_time = time.time() - start_time
    print(f"\nScene {scene_id} complete in {total_time:.0f}s")
    print(f"Individual clips: {clip_paths}")
    print(f"Final stitched video: {final_path}")
    return final_path


#ENTRY POINT
def main():
    from video_gen import load_env
    load_env()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found in .env")
        return

    from google import genai
    client = genai.Client(api_key=api_key)
    init_output_dir()

    scenario = load_scenario(SCENARIO_FILE)
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    scenes = scenario["scenes"]

    #test with scene 3 first, with sprites, 3 clips (~24 seconds)
    scene3 = next(s for s in scenes if s["scene_id"] == 3)
    run_scene_pipeline(
        client=client,
        scene=scene3,
        characters=characters,
        visual_style=visual_style,
        num_clips=3,
        use_reference_images=True,
    )


if __name__ == "__main__":
    main()