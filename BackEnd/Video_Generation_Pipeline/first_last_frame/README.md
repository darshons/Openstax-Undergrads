# First+Last-Frame Prototype

Prototype alternative to `video_generator`'s extension-chain pipeline. Instead of
extending each clip from the previous clip's video handle, each clip is generated
from a pinned **first frame** and **last frame** image via Veo's native
image-to-video-with-interpolation mode (`config.last_frame`). The goal is to check
whether pinning both endpoints of a clip reduces minor-character drift (lips,
extra limbs, prop jitter) compared to free-form extension.

Isolated from `video_generator/` — nothing here is wired into the main pipeline,
and it can be deleted without touching it.

## Scope / limitations

- Veo's image-to-video duration is capped at 4/6/8 seconds, so a scene is still
  split into per-clip chunks (default 8s each), same as the main pipeline.
- Clip N+1's first frame reuses clip N's generated last frame (image chaining) for
  continuity, rather than every clip's endpoints being generated independently.
- Output is one mp4 per clip, plus one stitched full-scene mp4 (via ffmpeg) if
  every clip in the scene succeeded. Requires `ffmpeg` on PATH.
- Multi-scene chaining and the transcript-eval system are out of scope. Use the
  main `video_generator` pipeline for those.

## Step 1: generate frame images (no Veo cost)

Run from `BackEnd/Video_Generation_Pipeline/`:

```bash
python -m first_last_frame.generate_images --scenario scenario.json --scene-id 1
```

For each clip in the scene, a Gemini text model (`gemini-2.5-flash`) first writes a
precise visual description of exactly what's on-screen at that instant (resolving
ambiguous blocking like "entering" — e.g. a character mid-entrance isn't yet fully
in frame), then that description is handed to the image model
(`gemini-3.1-flash-image`) alongside `reference_images/maya.png`,
`reference_images/carl.png`, and `reference_images/background_reference_image.png`
for character/background consistency. Writes:

- `output/first_last_frame/images/scene{id}_clip{n}_first.png`
- `output/first_last_frame/images/scene{id}_clip{n}_first_prompt.txt` — the
  generated visual prompt behind that image, for debugging blocking issues.
- `output/first_last_frame/images/scene{id}_clip{n}_last.png` (+ matching
  `_last_prompt.txt`)
- `output/first_last_frame/images/scene{id}_frame_manifest.json` — maps each
  clip to its first/last frame paths, read by step 2.

## Step 2: generate video clips (calls Veo — real cost)

```bash
python -m first_last_frame.generate_video --scenario scenario.json --scene-id 1
```

Reads the manifest from step 1, generates one Veo clip per entry (first frame +
last frame pinned, `--duration-seconds` default 8, must be 4/6/8), downloads each
clip to `output/first_last_frame/scene{id}_clip{n}_{timestamp}.mp4`, and logs one
entry per clip to `output/first_last_frame/flf_log.json`. If every clip in the
scene succeeded, stitches them in order into
`output/first_last_frame/scene{id}_stitched_{timestamp}.mp4` via ffmpeg.

Both steps require `GEMINI_API_KEY` (env var or `--api-key`), same as the main
pipeline's `.env` convention.
