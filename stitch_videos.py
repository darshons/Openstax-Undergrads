#!/usr/bin/env python3
"""
Stitch Pipeline
Generates videos using Veo's video extension feature. Each clip continues from the last second
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
#DURATION CONSTRAINTS
VALID_FIRST_CLIP_SECONDS = (4, 6, 8)
EXTENSION_SECONDS = 7
MAX_CLIPS = 21
#PROCESSING SETTLE - an extension's output isn't extend-eligible the instant the
#operation reports done; let it finish before chaining the next hop
EXTENSION_SETTLE_SECONDS = 15

#GENERATE FIRST CLIP
def generate_first_clip(client, prompt, clip_index=1, reference_images=None, duration_seconds=8):
    """
    Generates the opening clip for a scene.

    duration_seconds: 4, 6, or 8 - only when no reference images are used. 
    Asset/subject reference images force 8 second duration for veo-3.1-generate-preview, 
    so the value will get overridden in that case.

    Returns the Veo video object.
    """
    from google.genai import types
    from google.genai.types import VideoGenerationReferenceImage, Image as GenaImage

    #build reference image configs if provided
    ref_image_configs = []
    if reference_images:
        for img_path in reference_images:
            with open(img_path, "rb") as f:
                image_bytes = f.read()
            ref_image_configs.append(
                VideoGenerationReferenceImage(
                    image=GenaImage(image_bytes=image_bytes, mime_type="image/png"),
                    reference_type="asset",
                )
            )

    #reference images force 8 seconds on the preview model - that's okay
    if ref_image_configs and duration_seconds != 8:
        print(f" Note: reference images force 8s; ignoring duration_seconds={duration_seconds}")
        duration_seconds = 8

    print(f"\n Generating clip {clip_index} (first clip, {duration_seconds}s)...")

    operation = client.models.generate_videos(
        model=MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
            number_of_videos=1,
            duration_seconds=duration_seconds,
            reference_images=ref_image_configs if ref_image_configs else None,
        ),
    )

    operation = _poll_until_done(client, operation)
    return operation.response.generated_videos[0].video

#GENERATE EXTENSION CLIP
def generate_extension_clip(client, prompt, previous_video_obj, clip_index):
    """
    Extend the previous Veo video by one ~7s hop. Duration is NOT configurable on
    extension - the API returns a fixed ~7s continuation - so the clip's content
    must be written to fill ~7s. Continuity comes from the prior clip's final
    second, so no reference images here.
    """
    from google.genai import types

    print(f"\n  Generating clip {clip_index} (extension, ~7s)...")

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
    return operation.response.generated_videos[0].video

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
def download_video(client, video_obj, output_file):
    """ Download one Veo video object. Called once, on the final combined
    video — never on intermediate extension handles."""
    video_data = client.files.download(file=video_obj.uri)
    with open(output_file, "wb") as f:
        f.write(video_data)
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  Saved: {output_file} ({size_mb:.1f} MB)")
    return output_file

#ADD CLIP PROMPTS

def build_clip_prompts(scene, characters, visual_style):
    """
    Turn one scene into an ordered list of per-clip prompts (list[str]), one per
    clip. Each prompt carries the shared stage directions (setting, actions,
    camera, sound bed) plus only that clip's dialogue chunk
    """
    clips = scene.get("clips")
    if not clips:
        raise ValueError(f"Scene {scene.get('scene_id')} has no 'clips' to build clips from.")

    shared_audio = scene.get("audio", {})
    prompts = []
    for i, clip in enumerate(clips):
        #per-clip mini-scene: shared fields, clip overrides where present, this clip's dialogue only
        clip_scene = {
            "scene_id": scene.get("scene_id"),
            "setting": scene.get("setting", ""),
            "character_actions": clip.get("character_actions", scene.get("character_actions", "")),
            "camera": clip.get("camera", scene.get("camera", {})),
            "audio": {
                "dialogue": clip.get("dialogue", []),          #the repetition fix
                "sound_effects": shared_audio.get("sound_effects", "none"),
                "ambience": shared_audio.get("ambience", "none"),
            },
        }
        #on_screen_text is an "at end" overlay - only the final clip carries it
        if i == len(clips) - 1 and scene.get("on_screen_text"):
            clip_scene["on_screen_text"] = scene["on_screen_text"]

        prompts.append(build_veo_prompt(clip_scene, characters, visual_style))

    return prompts

#MAIN SCENE PIPELINE
def run_scene_pipeline(client, scene_id, clip_prompts, reference_images=None, first_clip_seconds=8):
    """
    Generate one scene as a single continuous video via Veo extension.

    clip_prompts: one prompt per clip, in order, built by build_clip_prompts.
    first_clip_seconds: 4/6/8 — only takes effect if reference_images is None.
    """
    num_clips = len(clip_prompts)
    if num_clips < 1:
        raise ValueError("clip_prompts is empty — nothing to generate.")
    if first_clip_seconds not in VALID_FIRST_CLIP_SECONDS:
        raise ValueError(f"first_clip_seconds must be one of {VALID_FIRST_CLIP_SECONDS}.")
    if num_clips > MAX_CLIPS:
        raise ValueError(
            f"{num_clips} clips exceeds Veo's extension ceiling of {MAX_CLIPS} "
            f"clips / ~148s. Split this scene before generating."
        )
    
    #reference images pin the opener to 8s, so reflect that in the estimate
    effective_first = 8 if reference_images else first_clip_seconds
    est_seconds = effective_first + (num_clips - 1) * EXTENSION_SECONDS

    print(f"\n{'─'*60}")
    print(f"SCENE {scene_id} — {num_clips} clips (~{est_seconds}s total)")
    print(f"{'─'*60}")

    start_time = time.time()

    video_obj = generate_first_clip(
        client, clip_prompts[0], clip_index=1,
        reference_images=reference_images, duration_seconds=first_clip_seconds,
    )
    
    i = 1
    try:
        for i, prompt in enumerate(clip_prompts[1:], start=2):
            video_obj = generate_extension_clip(client, prompt, video_obj, clip_index=i)
            #don't chain the next hop until this combined output has settled
            if i < num_clips:
                print(f"  Settling {EXTENSION_SETTLE_SECONDS}s before next hop...")
                time.sleep(EXTENSION_SETTLE_SECONDS)
    except Exception as e:
        #download the last good combined video so the spent hops aren't lost
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint = str(OUTPUT_DIR / f"scene{scene_id}_checkpoint_clip{i-1}_{ts}.mp4")
        download_video(client, video_obj, checkpoint)
        print(f"\n  Extension failed at clip {i}: {e}")
        print(f"  Last good video saved: {checkpoint}")
        raise

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sprite_label = "sprites" if reference_images else "no_sprites"
    final_path = str(OUTPUT_DIR / f"scene{scene_id}_final_{sprite_label}_{timestamp}.mp4")
    download_video(client, video_obj, final_path)

    print(f"\nScene {scene_id} complete in {time.time() - start_time:.0f}s")
    print(f"Final video: {final_path}")
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

    scene = next(s for s in scenes if s["scene_id"] == 3)

    #clip_prompts: one prompt per clip, built from this scene's clips.
    clip_prompts = build_clip_prompts(scene, characters, visual_style)  #<- yours to write

    run_scene_pipeline(
        client=client,
        scene_id=scene["scene_id"],
        clip_prompts=clip_prompts,
        reference_images=REFERENCE_IMAGES,
    )


if __name__ == "__main__":
    main()