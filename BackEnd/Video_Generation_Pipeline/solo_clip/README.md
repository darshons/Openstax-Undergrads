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
- `scene{id}_raw/{n}_{character_id}.mp4` — every raw solo clip before trimming
- `scene{id}_final.mp4` — the stitched scene video

## Module reference

| Module | Description |
|--------|-------------|
| `character_rig.py` | One Gemini text call deriving a fixed `{pose, backdrop, camera}` per character |
| `interaction_guard.py` | Detects gesture/interaction dialogue that empirically bleeds the other character into frame, and tightens framing on those lines |
| `reference_images.py` | Generates/caches character + background reference images via `Image_Generation_Pipeline` |
| `stitching.py` | Trims each clip to its speaking span (via Whisper) and hard-cuts them together with a declick fade |
| `clip_planner.py` | Breaks an authored scene into the `clips` breakdown this pipeline (and the main one) needs |
| `pipeline.py` | Orchestration: `run_scenario_pipeline_solo_clip` / `run_scene_pipeline_solo_clip` |
| `generate.py` | CLI entry point |
