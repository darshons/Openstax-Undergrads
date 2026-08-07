# Solo-Clip Technique

Alternative to `video_generator`'s extension-chain pipeline. Instead of chaining
every character into one shared, continuously-extended shot, each dialogue line is
rendered as its own isolated Veo clip — one character in frame, speaking, alone —
and the clips are stitched together afterward. This makes the wrong-speaker-in-
frame artifact the extension-chain pipeline is structurally prone to impossible
instead of something to prompt around.

Isolated from `video_generator/` — nothing here is wired into the main pipeline,
and it can be deleted without touching it. Modules import shared prompt-building
and Veo-call machinery from `video_generator` (`prompt_builder.build_veo_prompt`,
`veo_api.generate_first_clip`/`download_video`) rather than duplicating it.

## Scope / limitations

- Clips with zero dialogue lines (pure action/reaction beats) are skipped — there
  is no single "speaker" for a solo clip to isolate.
- No retry/escalation policy yet — a clip that raises is treated as a scene
  failure, same as the main pipeline; no automated visual QA or auto-retry-on-
  defect exists yet (still caught by human review only).
- Not wired into `--verify-clips`/`generation_log.json` — a run's only record is
  its console output and the files it writes to disk.
- Loses the main pipeline's shared two-shot camera coverage — every character
  gets one fixed pose/camera/backdrop for the whole scenario, reused identically
  across all their clips (see `character_rig.py`).

`prompt_builder.py` (shared with the main pipeline, not solo-clip-specific)
carries several guards worth knowing about since solo-clip prompts go through
it too: `distinguishing_features` (glasses, scars, etc.) is folded into both
the character description and the extension-clip consistency block; a
no-invented-props guard stops Veo from carrying over objects (e.g. a
clipboard) from reference images unless named in the current scene's
actions; a mouth-lock instruction keeps non-speaking characters' mouths
still; a dialogue-gated "clean and dry" voice-recording instruction only
fires when a clip actually has dialogue (asking Veo to "record dialogue" on
a silent clip is a contradictory prompt that empirically trips its audio
safety filter); a reference-image name-label warning stops the corner label
on portrait images from being rendered into the video; and a
default-to-nothing guard (camera lock, itemized no-unrequested-sound,
no-unrequested-visual-effects) closes out every prompt.

## How it works

```
generate.main()
  └─ reference_images.ensure_reference_images()   ← generate/cache character + background portraits
  └─ pipeline.run_scenario_pipeline_solo_clip()
       ├─ character_rig.generate_character_rig()  ← once per scenario: fixed pose/camera/backdrop per character
       └─ pipeline.run_scene_pipeline_solo_clip()  ← one scene → one stitched video
            ├─ interaction_guard.references_interaction()  ← tighter framing on gesture/interaction lines
            ├─ video_generator.veo_api.generate_first_clip()  ← one call per dialogue line (reference images
            │                                                    on a character's first appearance, first-frame
            │                                                    seeding from their own prior clip after that)
            └─ stitching.stitch()                 ← trim each clip to its speaking span, hard-cut concatenate
```

Every scene must already have a `clips` array with per-line `dialogue` entries,
same schema `video_generator` expects (see the root README's
[Scenario JSON schema](../README.md#scenario-json-schema)). `clip_planner.py` can
generate that breakdown from a flat authored scene if it doesn't exist yet.

**Consistency mechanism**, in order of how each character's clips are seeded:
- 1st appearance of a character in the scenario: Veo reference images (that
  character's portrait + the background image) — the same mechanism
  `video_generator` uses.
- Every later clip of that character: first-frame image conditioning, seeded from
  a frame extracted out of their most recent clean clip. Reference images and
  first-frame seeding are mutually exclusive per call (API-enforced), so this is
  an either/or choice per clip, not both.

## Quick start

Run from `BackEnd/Video_Generation_Pipeline/`:

```bash
# Generate one scene
python -m solo_clip.generate --scenario scenario.json --scene-id 1

# Generate all scenes
python -m solo_clip.generate --scenario scenario.json

# Override the default Veo model
python -m solo_clip.generate --scenario scenario.json --scene-id 1 --model veo-3.1-fast-generate-preview
```

Requires `GEMINI_API_KEY` (env var or `--api-key`), same as the main pipeline's
`.env` convention.

Writes to `output/solo_clip/`:
- `character_rig.json` — the derived pose/camera/backdrop per character, cached
  so a retry reuses the identical wording
- `reference_images/` — auto-generated/cached character + background portraits
- `scene{id}_raw/{n}_{character_id}.mp4` — every raw solo clip before trimming,
  each with a sidecar `{n}_{character_id}.txt` recording the exact line it was
  generated for (used by `stitching.py`, see below)
- `scene{id}_final.mp4` — the stitched scene video

### Reviewing output

`review_player.html` + `serve_review.py` (repo root of
`Video_Generation_Pipeline/`) is a standalone, build-free page that plays
`output/solo_clip/scene1..sceneN_final.mp4` in order for review. Plain
`python3 -m http.server` can't serve video for HTML5 playback (no Range
support), so `serve_review.py` is a small Range-request-supporting static
server instead:

```bash
python3 serve_review.py       # defaults to port 8934
# open http://localhost:8934/review_player.html
```

## Module reference

| Module | Description |
|--------|-------------|
| `character_rig.py` | One Gemini text call deriving a fixed `{pose, backdrop, camera}` per character, including a three-quarter portrait body/head rotation (not a straight-on gaze) to reduce bleed-through and direct-to-camera gaze |
| `interaction_guard.py` | Detects gesture/interaction dialogue that empirically bleeds the other character into frame, and tightens framing on those lines |
| `reference_images.py` | Generates/caches character + background reference images via `Image_Generation_Pipeline` |
| `stitching.py` | Trims each clip to its speaking span (via Whisper), using each clip's sidecar `.txt` to drop stray unscripted interjections (e.g. a filler "Oh.") that share no words with the expected line before computing the span; hard-cuts clips together with a declick fade; writes the final file with `-movflags +faststart` so it plays progressively over HTTP |
| `clip_planner.py` | Breaks an authored scene into the `clips` breakdown this pipeline (and the main one) needs |
| `pipeline.py` | Orchestration: `run_scenario_pipeline_solo_clip` / `run_scene_pipeline_solo_clip`. Lines of 7 words or fewer get an explicit no-invent/no-repeat instruction — Veo has been observed filling leftover clip time by repeating a short line a second time otherwise |
| `generate.py` | CLI entry point |

## API

`BackEnd/API/instructor_api.py` exposes the solo-clip technique as
`POST /instructor_api/generate_videos_v2` — same request shape
(`VisualGenerationRequest`) and status contract as the main pipeline's
`/generate_videos`, so `GET /instructor_api/video_status/{request_id}` polls
either one unchanged. Background job: `plan_scenario_clips` →
`run_scenario_pipeline_solo_clip`, writing `status.json`
(`planning_clips` → `rendering` → `done`/`completed_with_errors`/`failed`)
after every stage/scene transition. Veo-only for now — no local/Wan backend
counterpart, unlike v1's `backend="local"|"veo"` choice.
