# Solo-clip generation: one isolated Veo clip per speaking character per
# dialogue line - never two characters in the same shot - so the
# wrong-speaker artifact that the extension-chain pipeline (pipeline.py's
# run_scenario_pipeline) is structurally prone to becomes impossible instead
# of something to prompt around.
#
# Reuses each scene's existing `clips` breakdown (see scenario.json /
# clip_planner.py) as-is: every scene already carries scene["clips"], each
# clip already carrying a `dialogue` list of {"character_id", "line"}
# entries. This module just explodes that per-clip dialogue into one solo
# clip per line - no new planning step needed. A clip's authored
# `character_actions`/`camera` (written for a shared multi-character shot)
# are ignored entirely; every character instead gets one fixed pose/camera/
# backdrop for the whole scenario (character_rig.py), reused identically
# across every one of that character's clips so cuts between speakers read
# as distinct, consistent camera setups rather than a new composition each
# time.
#
# Consistency mechanism, in order of how each character's clips are seeded:
#   1st appearance of a character in the scenario: Veo reference_images
#      (that character's portrait + the background image) - the same
#      mechanism the extension-chain pipeline uses.
#   every later clip of that character: first-frame image conditioning,
#      seeded from a frame extracted out of their most recent clean clip.
#      Confirmed empirically to hold position/framing far more reliably
#      than repeating the same camera-framing text alone, and to reduce
#      (not eliminate) the cross-character bleed-through the text-only
#      approach could not fully solve. reference_images and first-frame
#      seeding are mutually exclusive per call (API-enforced), so this is
#      an either/or choice per clip, not both.
#
# Known v1 simplifications, not yet at parity with the extension-chain
# pipeline:
#   - Clips with zero dialogue lines (pure action/reaction beats) are
#     skipped - there is no single "speaker" for a solo clip to isolate.
#   - Automated visual/dialogue QA is opt-in via verify_clips (transcript_eval's
#     video judge, same as the extension-chain pipeline), regenerating a
#     failing clip in place up to eval_retries times; a clip that still fails
#     after that is treated as a scene failure, same as any other raise.
import io
import os
import time
from pathlib import Path

from video_generator.clip_verification import eval_failure_reason
from video_generator.prompt_builder import build_veo_prompt
from video_generator.veo_api import ClipEvalFailedError, download_video, generate_first_clip

# clip_verification (imported above) already inserts Transcript_Eval_Pipeline
# onto sys.path, making transcript_eval importable here too.
from transcript_eval.video_judge import evaluate_clip

from .character_rig import generate_character_rig, load_cached_rig, rig_cache_path, save_rig_cache, setting_summary
from .interaction_guard import close_up_camera, interaction_isolation_instruction, references_interaction
from .stitching import stitch

FIRST_CLIP_SECONDS = 8
# Scene 10's instructor line ("What did you find with Elena?", 6 words) is
# the shortest line in the whole scenario and sat one word above the old
# limit of 5 - Veo filled the leftover time in the 8s clip by repeating the
# line a second time instead of reacting silently. Raised to 7 so every line
# that short gets the no-invent guard below.
SHORT_LINE_WORD_LIMIT = 7
SEED_FRAME_TIMESTAMP_FRACTION = 0.2  # early in the clip - more likely a neutral, not mid-word, moment

NO_INVENT_INSTRUCTION = (
    "Do not invent, add, or extend any spoken dialogue beyond the single line "
    "specified above, and do not repeat that line a second time. After "
    "delivering it once, {name} simply reacts naturally (a small gesture, "
    "posture shift, or expression change) for the rest of the clip."
)


def _other_character_reinforcement(speaker_name: str, other_names: list) -> str:
    if not other_names:
        return ""
    others_text = " or ".join(other_names)
    lines = [
        f"{name} is not in this shot, full stop - not their face, not their "
        f"back, not their shoulder or hair, not a blurry or out-of-focus "
        f"shape, not any part of them anywhere in frame at any point in the "
        f"clip. Treat this as though {speaker_name} is alone in the room for "
        "filming purposes, even though the scene describes multiple people present."
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
        + f"\n\nFraming detail: this is a clean, isolated character portrait "
        f"shot, not a conversation over-the-shoulder shot. There is nothing "
        f"at all positioned between the camera and {speaker_name} and "
        f"nothing in the foreground of the frame - no blurred shape, no "
        f"soft-focus head or shoulder, no second silhouette of any kind "
        f"anywhere in the frame, foreground or background. The area to the "
        f"left and right of {speaker_name} is empty wall only. "
        f"{speaker_name} is the only person the camera can see, filmed as "
        "if no one else is in the room."
    )


def _flatten_scene_lines(scene: dict) -> list:
    """One entry per dialogue line across every clip in the scene, in
    original order. Clips with no dialogue (pure action beats) contribute
    nothing - see module docstring."""
    lines = []
    for clip in scene.get("clips") or []:
        lines.extend(clip.get("dialogue", []))
    return lines


def _spoken_text(line_text: str) -> str:
    """Some scripts embed the speaker's action/narration directly in the
    dialogue line's text (e.g. "Caleb greets the patient by saying: Good
    morning.") rather than as a separate field. Only the part after that
    framing is meant to be spoken - left as-is, Veo reads the narration
    itself aloud verbatim, which is what produces that stilted,
    over-narrated delivery. Falls back to the original text if there's no
    colon to split on (e.g. scripts that already author clean quotes)."""
    prefix, sep, rest = line_text.partition(":")
    return rest.strip() if sep and rest.strip() else line_text


def _build_line_prompt(
    scene: dict, characters: list, visual_style: str, rig: dict, line: dict, setting_text: str
) -> tuple:
    """Returns (prompt, speaker_id, interaction_flagged)."""
    char_lookup = {c["character_id"]: c for c in characters}
    speaker_id = line["character_id"]
    speaker = char_lookup[speaker_id]
    others = [c for c in characters if c["character_id"] != speaker_id]
    other_names = [c["name"] for c in others]
    # references_interaction scans the full original line, not just the
    # spoken part - action cues like "nods and says" live in the narration
    # half that _spoken_text strips out below.
    interaction_flagged = references_interaction(line["line"])
    spoken_text = _spoken_text(line["line"])

    camera = (
        close_up_camera(speaker["name"], rig[speaker_id]["backdrop"])
        if interaction_flagged
        else rig[speaker_id]["camera"]
    )
    line_scene = {
        # Same stable room description the rig's fixed backdrops were derived
        # from - not the scene's narrative scene_summary, which describes
        # transient action (e.g. a character "entering") that contradicts a
        # backdrop meant to look identical across every clip.
        "setting": setting_text,
        "character_actions": rig[speaker_id]["pose"],
        "camera": camera,
        "audio": {
            "dialogue": [{"character_id": speaker_id, "line": spoken_text}],
            # `or "none"` (not just .get(..., "none")) since an authored scene
            # can carry an explicit empty string here, which would otherwise
            # render as a malformed "Sound effects: ." fragment in the prompt.
            "sound_effects": scene.get("audio", {}).get("sound_effects") or "none",
            "ambience": scene.get("audio", {}).get("ambience") or "none",
        },
    }
    # Only the speaker's own appearance is described - the other characters'
    # full physical descriptions have no reason to be in a prompt for a shot
    # they're not supposed to appear in at all.
    prompt = build_veo_prompt(line_scene, [speaker], visual_style, is_continuation=False)
    if other_names:
        prompt = f"{prompt}\n\n{_other_character_reinforcement(speaker['name'], other_names)}"
    if interaction_flagged and other_names:
        others_text = " or ".join(other_names)
        prompt = f"{prompt}\n\n{interaction_isolation_instruction(speaker['name'], others_text)}"

    word_count = len(spoken_text.split())
    if word_count <= SHORT_LINE_WORD_LIMIT:
        prompt = f"{prompt}\n\n{NO_INVENT_INSTRUCTION.format(name=speaker['name'])}"

    return prompt, speaker_id, interaction_flagged


def _extract_seed_frame(video_path: Path) -> bytes:
    from moviepy import VideoFileClip
    from PIL import Image

    video = VideoFileClip(str(video_path))
    t = min(SEED_FRAME_TIMESTAMP_FRACTION * video.duration, video.duration - 0.1)
    frame = video.get_frame(t)
    video.close()

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="PNG")
    return buf.getvalue()


def _find_latest_existing_clip(output_dir: Path, character_id: str) -> Path | None:
    """Finds the most recently generated raw clip for a character already on
    disk, e.g. from a prior partial run. Lets a retry pick up first-frame
    seeding where it left off instead of falling back to reference_images
    for a character who's already established."""
    candidates = list(output_dir.glob(f"scene*_raw/*_{character_id}.mp4"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _generate_and_verify_solo_clip(
    client,
    prompt,
    reference_images,
    seed_bytes,
    model,
    video_path: Path,
    failed_dir: Path,
    verify_clips: bool,
    eval_retries: int,
    scene_id: int,
    clip_id: int,
    speaker: dict,
    line: dict,
    setting_text: str,
    character_actions: str,
):
    """Generates one solo clip, downloads it to video_path, and — if
    verify_clips — judges it with transcript_eval, regenerating in place
    (same prompt/seed) up to eval_retries more times on failure. Unlike the
    extension-chain pipeline, a solo clip isn't chained to the ones after
    it, so a bad clip is retried on its own instead of restarting the whole
    scene. Only characters=[speaker] is passed to the judge since every
    other character is instructed to be entirely absent from a solo shot.

    A clip that fails eval is moved into failed_dir (same "keep discarded
    attempts for review" convention as the extension-chain pipeline's
    failed_clips/) rather than silently overwritten by the next attempt's
    download to video_path.
    """
    attempts = eval_retries + 1 if verify_clips else 1
    for attempt in range(attempts):
        video_obj, _attempts, _recovered_error = generate_first_clip(
            client,
            prompt,
            clip_index=clip_id,
            reference_images=reference_images,
            seed_image_bytes=seed_bytes,
            duration_seconds=FIRST_CLIP_SECONDS,
            model=model,
        )
        download_video(client, video_obj, str(video_path))

        if not verify_clips:
            return video_obj

        report = evaluate_clip(
            client,
            video_path=str(video_path),
            scene_id=scene_id,
            clip_id=clip_id,
            dialogue=[line],
            characters=[speaker],
            setting=setting_text,
            character_actions=character_actions,
        )
        if report["passed"]:
            return video_obj

        ts = time.strftime("%Y%m%d_%H%M%S")
        failed_dir.mkdir(parents=True, exist_ok=True)
        kept_path = failed_dir / f"{video_path.stem}_attempt{attempt + 1}_{ts}{video_path.suffix}"
        os.replace(video_path, kept_path)

        print(f"  Clip {clip_id} failed eval: {eval_failure_reason(report)}")
        print(f"  Failed attempt saved: {kept_path}")
        if attempt < attempts - 1:
            print(f"  Regenerating clip {clip_id} (attempt {attempt + 2}/{attempts})...")

    raise ClipEvalFailedError(f"clip {clip_id}: {eval_failure_reason(report)}")


def run_scene_pipeline_solo_clip(
    client,
    scene: dict,
    characters: list,
    visual_style: str,
    rig: dict,
    character_image_file_mapping: dict,
    background_image_path: str,
    seed_bytes_by_character: dict,
    output_dir: Path,
    setting_text: str,
    model: str = None,
    verify_clips: bool = False,
    eval_retries: int = 1,
) -> str:
    """Generates every solo clip for one scene and stitches them together.
    seed_bytes_by_character is mutated in place (shared across scenes in a
    scenario) so a character's first clip anywhere in the run establishes
    the seed reused for every later appearance, scene boundaries included.
    Returns the path to the final stitched scene video."""
    scene_id = scene["scene_id"]
    lines = _flatten_scene_lines(scene)
    char_lookup = {c["character_id"]: c for c in characters}

    raw_dir = output_dir / f"scene{scene_id}_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    failed_dir = output_dir / "failed_clips"

    for i, line in enumerate(lines, start=1):
        prompt, speaker_id, _ = _build_line_prompt(scene, characters, visual_style, rig, line, setting_text)

        seed_bytes = seed_bytes_by_character.get(speaker_id)
        reference_images = None
        if seed_bytes is None:
            reference_images = [character_image_file_mapping[speaker_id], background_image_path]

        video_path = raw_dir / f"{i:02d}_{speaker_id}.mp4"
        _generate_and_verify_solo_clip(
            client,
            prompt,
            reference_images,
            seed_bytes,
            model,
            video_path,
            failed_dir,
            verify_clips,
            eval_retries,
            scene_id,
            i,
            char_lookup[speaker_id],
            line,
            setting_text,
            rig[speaker_id]["pose"],
        )
        # Sidecar recording the exact spoken text this clip was generated
        # for, so stitching can tell a stray unscripted interjection Veo
        # sometimes tacks on (e.g. a filler "Oh." before/after the real
        # line) apart from the actual line, instead of blindly trimming to
        # the full first-detected-speech-to-last-detected-speech span.
        video_path.with_suffix(".txt").write_text(_spoken_text(line["line"]), encoding="utf-8")

        if seed_bytes is None:
            seed_bytes_by_character[speaker_id] = _extract_seed_frame(video_path)

    output_path = output_dir / f"scene{scene_id}_final.mp4"
    stitch(raw_dir, output_path)
    return str(output_path)


def run_scenario_pipeline_solo_clip(
    client,
    scenario: dict,
    character_image_file_mapping: dict,
    background_image_path: str,
    output_dir: Path,
    model: str = None,
    on_scene_complete=None,
    verify_clips: bool = False,
    eval_retries: int = 1,
) -> list:
    """Solo-clip counterpart to pipeline.py's run_scenario_pipeline. Derives
    the character rig once (one cheap LLM call, not per scene), then renders
    and stitches every scene in order. Per-scene failures are isolated -
    one scene raising doesn't stop the rest, matching the extension-chain
    pipeline's behavior - and reported the same way via on_scene_complete so
    callers don't need to change their status-tracking logic.

    The rig is cached to output_dir so a retry of a partially-failed run
    (e.g. after a transient Veo error) reuses the identical pose/backdrop
    text rather than re-deriving a fresh one that could word things
    slightly differently. Retries also pick up first-frame seeding from
    whatever clips already exist on disk for each character, instead of
    falling back to reference_images for a character who's already
    established.
    """
    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    output_dir = Path(output_dir)

    cache_path = rig_cache_path(output_dir)
    rig = load_cached_rig(cache_path)
    # A cached rig from a different scenario sharing the same output_dir
    # (e.g. output/solo_clip/ reused across runs) silently passes the
    # existence check above but is missing this scenario's character_ids -
    # rig[speaker_id] then raises a bare KeyError deep in _build_line_prompt.
    # Regenerate whenever the cache doesn't cover every character actually
    # in this scenario, rather than trusting staleness-blind presence alone.
    if rig is not None and not set(c["character_id"] for c in characters) <= rig.keys():
        rig = None
    if rig is None:
        rig = generate_character_rig(client, scenario)
        save_rig_cache(cache_path, rig)
    setting_text = setting_summary(scenario)

    seed_bytes_by_character = {}
    for character_id in character_image_file_mapping:
        existing_clip = _find_latest_existing_clip(output_dir, character_id)
        if existing_clip is not None:
            seed_bytes_by_character[character_id] = _extract_seed_frame(existing_clip)

    results = []
    for scene in scenario["scenes"]:
        scene_id = scene["scene_id"]
        try:
            output_file = run_scene_pipeline_solo_clip(
                client=client,
                scene=scene,
                characters=characters,
                visual_style=visual_style,
                rig=rig,
                character_image_file_mapping=character_image_file_mapping,
                background_image_path=background_image_path,
                seed_bytes_by_character=seed_bytes_by_character,
                output_dir=output_dir,
                setting_text=setting_text,
                model=model,
                verify_clips=verify_clips,
                eval_retries=eval_retries,
            )
            result = {"scene_id": scene_id, "success": True, "output_file": output_file, "error": None}
        except Exception as e:
            result = {"scene_id": scene_id, "success": False, "output_file": None, "error": str(e)}

        results.append(result)
        if on_scene_complete:
            on_scene_complete(result)

    return results
