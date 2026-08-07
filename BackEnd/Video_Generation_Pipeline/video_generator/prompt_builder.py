def build_character_block(characters: list) -> str:
    char_lookup = {c["character_id"]: c for c in characters}
    char_lines = []
    for cid, char in char_lookup.items():
        a = char["appearance"]
        distinguishing = a.get("distinguishing_features")
        line = (
            f"{char['name']} ({char['role']}): "
            f"{a['skin_tone']} skin, {a['hair']}, {a['uniform']}"
        )
        if distinguishing:
            line += f", {distinguishing}"
        line += f". Emotional tone: {char['emotional_baseline']}."
        char_lines.append(line)
    return " | ".join(char_lines)


def build_dialogue_block(scene: dict, char_lookup: dict) -> str:
    dialogue_entries = scene.get("audio", {}).get("dialogue", [])
    dialogue_lines = []
    for idx, line in enumerate(dialogue_entries, start=1):
        char = char_lookup.get(line["character_id"])
        name = char["name"] if char else line["character_id"]
        dialogue_lines.append(f'{idx}. {name}: "{line["line"]}"')

    if dialogue_lines:
        return (
            "Spoken in this exact order — each character delivers only their own numbered line:\n    "
            + "\n    ".join(dialogue_lines)
            + "\n    Do not swap, merge, or reorder lines between characters."
        )
    return (
        "None — no spoken words in this clip. "
        "All characters act and react silently. Do not invent dialogue."
    )


def build_veo_prompt(
    scene: dict,
    characters: list,
    visual_style: str,
    is_continuation: bool = False,
) -> str:
    """
    Converts scene, character descriptions, and visual style from JSON into a prompt for Veo.

    is_continuation:
        False = first clip, reference images are passed.
        True  = extension clip, previous video is passed instead of reference images.

    Reference images are only available for the first clip. Extension clips should not
    claim that reference images are provided.
    """
    char_lookup = {c["character_id"]: c for c in characters}

    character_block = build_character_block(characters)
    dialogue_block = build_dialogue_block(scene, char_lookup)

    cam = scene.get("camera", {})
    camera_block = (
        f"{cam.get('angle', '')}. "
        f"{cam.get('movement', '')}. "
        f"{cam.get('lens_effect', '')}."
    )

    audio = scene.get("audio", {})
    sound_block = (
        f"Sound effects: {audio.get('sound_effects', 'none')}. "
        f"Ambience: {audio.get('ambience', 'none')}."
    )
    # Only applies when there's actual dialogue - instructing Veo how to
    # "record the dialogue voice" on a clip with no dialogue at all is a
    # contradictory ask that may be what's tripping Veo's audio safety
    # filter on silent multi-character clips (empty-response failures,
    # "issue with the audio for your prompt", seen repeatedly on scene 8's
    # silent two-shot attempts).
    if scene.get("audio", {}).get("dialogue"):
        sound_block += (
            " Dialogue voice recording: clean and dry, as if captured by a "
            "boom microphone close to the speaker - minimal room reverb, "
            "echo, or hollow/hall-like resonance on the voice, even though "
            "the room itself has hard surfaces."
        )

    # Reference images are only passed for the first clip.
    has_reference_images = not is_continuation

    # ------------------------------------------------------------------
    # First clip: full prompt
    # ------------------------------------------------------------------
    if not is_continuation:
        prompt = f"""Visual style: {visual_style}

Characters: {character_block}

Setting: {scene.get('setting', '')}

Character actions: {scene.get('character_actions', '')}

Camera: {camera_block}

Dialogue: {dialogue_block}

Audio: {sound_block}"""

        if scene.get("on_screen_text"):
            prompt += (
                f"\n\nOn-screen text overlay at end: \"{scene['on_screen_text']}\""
            )

        consistency_lines = []
        for char in characters:
            a = char["appearance"]
            distinguishing = a.get("distinguishing_features")
            line = (
                f"{char['name']} always wears {a['uniform']}; "
                f"{a['skin_tone']} skin, {a['hair']}"
            )
            if distinguishing:
                line += f"; always has {distinguishing}"
            line += (
                f". Do not change {char['name']}'s clothing, hair, skin tone, "
                "facial features, or distinguishing features at any point - "
                "these must be identical in every single shot."
            )
            consistency_lines.append(line)

        if has_reference_images:
            prompt += "\n\nCharacter reference images are provided. "

        prompt += (
            " ".join(consistency_lines)
            + " Do not introduce any additional characters into frame."
            + " Characters only hold or interact with props explicitly described in"
            " the character actions above. Do not add, invent, or carry over any"
            " other object (e.g. a clipboard, tablet, or pen) from the reference"
            " images unless that prop is named in the current scene's actions."
        )

    # ------------------------------------------------------------------
    # Extension clips: compressed continuation prompt
    # ------------------------------------------------------------------
    else:
        prompt = f"""This clip is a direct continuation of the previous video. Do not reset the scene.

Use the established character appearances from the previous video. Preserve the same clothing, hair, skin tone, facial features, lighting, room layout, environment, and overall visual style. Do not reintroduce or redesign any character or object.

Current character actions: {scene.get('character_actions', '')}

Camera: {camera_block}

Dialogue: {dialogue_block}

Audio: {sound_block}

Do not introduce any additional characters into frame."""

        if scene.get("on_screen_text"):
            prompt += (
                f"\n\nOn-screen text overlay at end: \"{scene['on_screen_text']}\""
            )

    prompt += (
        "\n\nOnly the speaker's mouth should be moving while speaking. "
        "All other characters should have their mouth closed and not have any lip movement, "
        "remaining silent. Keep the background still and minimal."
    )

    # ------------------------------------------------------------------
    # Text overlay control
    # ------------------------------------------------------------------
    if scene.get("on_screen_text"):
        prompt += (
            "\n\nDo not include any other text overlays, captions, or subtitles "
            "beyond the specified on-screen text at the end."
        )
    else:
        prompt += (
            "\n\nDo not include any text overlays, captions, subtitles, "
            "or on-screen text in the video."
        )

    if has_reference_images:
        prompt += (
            " The character reference images each have a name label "
            "printed in the corner for identification purposes only - "
            "that label is not part of the scene. Do not render, copy, "
            "or reproduce that text, or any other text from the "
            "reference images, anywhere in the video."
        )

    # ------------------------------------------------------------------
    # Default-to-nothing: only render what is explicitly described above.
    # ------------------------------------------------------------------
    prompt += (
        "\n\nDo not add anything that is not explicitly described above. "
        "Camera lock: the camera does not zoom, pan, tilt, dolly, shake, or "
        "move in any way during this clip beyond what the Camera line above "
        "specifies - if it says static, the framing is pixel-identical from "
        "the first frame to the last, with no gradual zoom or drift. "
        "No unrequested sound, no exceptions: the only audio in this clip is "
        "the dialogue explicitly quoted above (if any) and the sound "
        "effects/ambience explicitly named in the Audio line above - nothing "
        "else. Specifically, do not add any of the following unless it is "
        "explicitly named in the Audio line: clicks, pops, beeps, dings, "
        "chimes, whooshes, static, hums, drones, musical stings, background "
        "music, notification sounds, mechanical/electronic noises, or any "
        "other sound effect - including after the dialogue ends, in the "
        "silence before it starts, or layered underneath it. If the Audio "
        "line says 'none' for sound effects, the clip contains zero sound "
        "effects of any kind, at any point, full stop. "
        "No unrequested visual effects: do not add vignettes, lens "
        "flares, flashes, film grain changes, color grading shifts, "
        "transitions, or any other screen effect that is not explicitly "
        "described above."
    )

    return prompt.strip()


def build_clip_prompts(scene: dict, characters: list, visual_style: str) -> list:
    """
    Turn one scene into an ordered list of per-clip prompts (list[str]), one per
    clip. Each prompt carries the shared stage directions (setting, actions,
    camera, sound bed) plus only that clip's dialogue chunk.
    """
    clips = scene.get("clips")
    if not clips:
        raise ValueError(
            f"Scene {scene.get('scene_id')} has no 'clips' to build clips from."
        )

    shared_audio = scene.get("audio", {})
    prompts = []
    for i, clip in enumerate(clips):
        clip_camera = clip.get("camera")
        if clip_camera is None:
            print(
                f"  [scene {scene.get('scene_id')} clip {clip.get('clip_id', i+1)}] No per-clip camera — using scene-level camera."
            )
            clip_camera = scene.get("camera", {})

        clip_scene = {
            "scene_id": scene.get("scene_id"),
            "setting": clip.get("setting", scene.get("setting", "")),
            "character_actions": clip.get(
                "character_actions", scene.get("character_actions", "")
            ),
            "camera": clip_camera,
            "audio": {
                "dialogue": clip.get("dialogue", []),
                "sound_effects": clip.get(
                    "sound_effects", shared_audio.get("sound_effects", "none")
                ),
                "ambience": clip.get("ambience", shared_audio.get("ambience", "none")),
            },
        }
        # on_screen_text is an "at end" overlay - only the final clip carries it
        if i == len(clips) - 1 and scene.get("on_screen_text"):
            clip_scene["on_screen_text"] = scene["on_screen_text"]

        prompts.append(
            build_veo_prompt(
                clip_scene, characters, visual_style, is_continuation=(i > 0)
            )
        )

    return prompts
