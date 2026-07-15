# video_generator

Generates MP4 videos from a scenario JSON file using Google Veo. Every scene is treated as a chain of extension clips — each clip continues from the last frame of the previous one — producing a single seamless video per scene.

---

## Module structure

```
video_generator/
  scenario_loader.py   — load and validate the scenario JSON
  prompt_builder.py    — convert scene data into Veo prompt strings
  veo_api.py           — Veo API calls, polling, retry, and download
  pipeline.py          — scene and scenario orchestration
  clip_verification.py — bridges to Transcript_Eval_Pipeline for --verify-clips
  logging_utils.py     — generation log, prompt saving, checkpoints
  cli.py               — argument parsing, entry point, caption burning

reference_images/      — place character reference PNGs here
output/                — generated videos and generation_log.json (created on first run)
  failed_clips/         — videos for clip attempts that failed --verify-clips eval (created on first use)
```

---

## Quick start

```bash
# First follow the README in the root directory to set up backend
cd Video_Generation_Pipeline

# Generate one scene
python -m video_generator.cli --scenario scenario.json --scene-id 3

# Generate all scenes
python -m video_generator.cli --scenario scenario.json

# Preview the per-clip prompts without generating
python -m video_generator.cli --scenario scenario.json --scene-id 3 --preview-prompt

# Generate and burn dialogue captions onto the output video
python -m video_generator.cli --scenario scenario.json --add-captions

# Generate with per-clip transcript/consistency verification, regenerating failed clips [Default retry is 1 time for each clip if failed]
python -m video_generator.cli --scenario scenario.json --scene-id 3 --verify-clips

# Generate with per-clip transcript/consistency verification, regenerating failed clips [maximum retries time is 2 for each clip]
python -m video_generator.cli --scenario scenario.json --scene-id 3 --verify-clips --eval-retries 2
```

Output videos are saved to `output/`. A generation log is written to `output/generation_log.json` after every run.

---

## Configuration

Model, resolution, aspect ratio, and reference images are set as constants at the top of `veo_api.py` — not as CLI flags.

| Constant | Default | Description |
|----------|---------|-------------|
| `MODEL` | `veo-3.1-generate-preview` | Veo model used for all clips |
| `MODEL_KEY` | `veo-3.1` | Short key used for logging and cost lookup |
| `RESOLUTION` | `720p` | `720p`, `1080p`, or `4k` |
| `ASPECT_RATIO` | `16:9` | `16:9` or `9:16` |
| `REFERENCE_IMAGES` | `[]` | Paths to character reference PNGs (first clip only) |
| `MAX_CLIPS` | `21` | Hard ceiling on clips per scene (~148 s) |
| `EXTENSION_SECONDS` | `7` | Duration added by each extension hop |
| `EXTENSION_SETTLE_SECONDS` | `15` | Settle delay between consecutive extension calls |
| `MAX_GENERATION_RETRIES` | `4` | Max retries on transient failures |

### Reference images

Drop PNG files in `reference_images/` and list them in `veo_api.py`:

```python
REFERENCE_IMAGES = ["reference_images/maya.png", "reference_images/carl.png"]
```

Reference images pin character appearance on the first clip only. Extension clips inherit appearance from the previous video.

---

## CLI flags

| Flag | Description |
|------|-------------|
| `--scenario` *(required)* | Path to the scenario JSON file |
| `--scene-id` | Generate only this scene ID; omit to generate all scenes |
| `--preview-prompt` | Print the per-clip prompts; skip API call |
| `--add-captions` | Burn dialogue captions onto the generated video (requires `moviepy`) |
| `--verify-clips` | Transcribe and evaluate each clip against the script as it's generated, regenerating on failure (see [Clip verification](#clip-verification)) |
| `--eval-retries` | Max regeneration attempts for a clip that fails `--verify-clips` eval (default: `1`) |
| `--api-key` | Gemini API key (default: `$GEMINI_API_KEY`) |

---

## Scenario JSON schema

The pipeline expects a JSON file with this top-level shape:

```json
{
  "title": "string",
  "learning_goal": "string",
  "target_audience": "string",
  "total_duration_seconds": 75,
  "visual_style": "string — animation style guide fed verbatim into every prompt",
  "characters": [...],
  "scenes": [...],
  "decision_points": [...]
}
```

### Characters

```json
{
  "character_id": "nurse_maya",
  "name": "Maya",
  "role": "Nursing student",
  "appearance": {
    "skin_tone": "Medium warm brown",
    "hair": "Dark brown, pulled back in a low bun",
    "build": "Average height, slim to medium build",
    "uniform": "Light blue scrub top and matching pants"
  },
  "emotional_baseline": "Attentive, calm, professionally warm"
}
```

### Scenes

Every scene must have a `clips` array. Each clip becomes one Veo API call.

```json
{
  "scene_id": 1,
  "type": "narrative",
  "duration_seconds": 28,
  "setting": "Single-occupancy hospital room...",
  "character_actions": "Maya enters from the left...",
  "camera": {
    "angle": "Medium two-shot",
    "movement": "Static",
    "lens_effect": "Slightly warm, neutral depth"
  },
  "audio": {
    "sound_effects": "Soft ambient hospital sounds",
    "ambience": "Quiet hospital room"
  },
  "clips": [...],
  "on_screen_text": null,
  "routes_to": { "type": "decision_point", "decision_point_id": 1 }
}
```

Each clip carries its own `dialogue`, `character_actions`, and `camera` override:

```json
{
  "clip_id": 1,
  "dialogue": [
    { "character_id": "nurse_maya", "line": "Good morning, Carl." }
  ],
  "character_actions": "Maya enters from the left...",
  "camera": { "angle": "Medium two-shot", "movement": "Static", "lens_effect": "Warm" }
}
```

`on_screen_text` is placed only on the final clip. All other clips suppress text overlays.

The first clip gets a full prompt (setting, characters, camera, dialogue). Extension clips get a compressed continuation prompt that instructs Veo not to reset any visual element.

### Decision points

```json
{
  "decision_point_id": 1,
  "question_text": "Carl says he's fine, but his arms are crossed...",
  "choices": [
    {
      "choice_id": "A",
      "text": "Name what you observed and ask Carl directly.",
      "is_correct": true,
      "misconception": null,
      "routes_to_scene": 3
    },
    {
      "choice_id": "B",
      "text": "Reassure him that everything will be okay.",
      "is_correct": false,
      "misconception": "Providing false reassurance is a nontherapeutic response...",
      "routes_to_scene": 2
    }
  ]
}
```

Decision points drive frontend branching; the video pipeline generates all scenes independently and ignores them.

---

## Generation pipeline

```
cli.main()
  └─ pipeline.run_scenario_pipeline()        ← iterates all scenes
       └─ pipeline.run_scene_pipeline()      ← one scene → one video
            ├─ prompt_builder.build_clip_prompts()
            ├─ veo_api.generate_first_clip()        ← clip 1 (4/6/8 s)
            ├─ veo_api.generate_extension_clip()    ← clip 2 (~7 s)
            ├─ veo_api.generate_extension_clip()    ← clip 3 (~7 s)  ...
            └─ veo_api.download_video()             ← final combined video
```

If an extension fails mid-scene, the last successful combined video is saved as a checkpoint (`scene{N}_checkpoint_clip{K}_{ts}.mp4`) and logged so spent API calls are not lost.

---

## Clip verification

`--verify-clips` wires in [`Transcript_Eval_Pipeline`](../Transcript_Eval_Pipeline/README.md) to check each clip's actual dialogue and on-screen speaker against `scenario.json` *as it's generated*, not after the fact — so a bad clip gets caught (and optionally regenerated) before the pipeline spends further Veo extension calls building on top of it.

**Why this needs an extra step (cumulative vs. incremental video):** Veo's extension API is cumulative — `generate_extension_clip()` returns the *entire video so far* (all previous clips + the new one), never an isolated new segment (see `download_video`'s docstring: "never on intermediate extension handles"). `Transcript_Eval_Pipeline`, however, evaluates one isolated clip at a time. So `clip_verification.py` bridges the two:

```
pipeline._generate_and_verify()
  ├─ veo_api.generate_first_clip() / generate_extension_clip()   ← cumulative video_obj
  ├─ clip_verification.verify_clip()
  │    ├─ veo_api.download_video()            ← download the cumulative video to a temp file
  │    ├─ veo_api.get_video_duration()         ← measure it
  │    ├─ clip_verification.extract_new_segment()   ← trim [prev_duration, new_duration) — just the new clip
  │    ├─ transcript_eval.eval.evaluate_clip()  ← transcribe + evaluate the isolated clip
  │    ├─ delete the temp cumulative download (always redundant once isolated)
  │    └─ delete the isolated clip video too, but only if eval passed
  ├─ log_generation() — one generation_log.json entry for THIS attempt, pass or fail
  └─ on failure: regenerate the same clip (same prompt, same base video) up to --eval-retries times,
     then raise ClipEvalFailedError if still failing
```

`prev_duration`/`new_duration` are the actual measured durations of each successive cumulative download (via `get_video_duration`), not hardcoded per-clip lengths — this handles the first clip legitimately having a different length (4/6/8 s) than extension clips (~7 s each).

On exhausted retries, `ClipEvalFailedError` flows through the same checkpoint/logging path as a Veo API failure (see [Generation pipeline](#generation-pipeline) above) — the last known-*good* cumulative video (before the failing clip) is checkpointed, one final `generation_log.json` entry records `error_type: "content_eval_failed"` for the scene, and the scene is marked failed in the run summary. A first-clip eval failure has no prior good video to checkpoint, so it propagates straight to `run_scenario_pipeline`'s per-scene handler instead.

**Every clip-generation attempt is logged, not just the scene's final outcome.** `_log_clip_attempt()` calls `log_generation()` once per attempt (see [Generation log](#generation-log) below for the per-attempt fields) — a clip that fails eval and gets regenerated leaves a full record of *every* take, including ones that never made it into the final video:

- A **passed** attempt's isolated clip video is deleted (its content already lives on in the ongoing cumulative video, no need to duplicate storage) — the log entry's `output_file` is `null`, but `eval_report_path` still points to the full `transcript_eval` report.
- A **failed** attempt's isolated clip video is kept — relocated (not renamed, so its filename stem still matches its `transcript_eval` report) from the temp dir into `output/failed_clips/`, so the log entry's `output_file` points to something you can actually watch.

**Cost/latency**: `--verify-clips` is opt-in because it changes the pipeline's cost profile — it downloads the cumulative video after *every* clip (not just once at the end) and adds a Gemini vision judge call per clip via `transcript_eval`'s speaker-attribution stage. Whisper transcription itself stays free/local. A clip that needs retries multiplies this cost by the number of attempts, and failed attempts now also accumulate disk usage under `output/failed_clips/` (not automatically cleaned up).

---

## Generation log

Every completed scene is appended to `output/generation_log.json` (this shape is unchanged from before `--verify-clips` existed — `clip_id`/`attempt_number`/`eval_passed`/`eval_report_path` are simply `null` here):

```json
{
  "timestamp":              "2025-01-15T14:32:10.123",
  "scene_id":               1,
  "clip_id":                null,
  "attempt_number":         null,
  "model":                  "veo-3.1",
  "model_api_name":         "veo-3.1-generate-preview",
  "resolution":             "720p",
  "aspect_ratio":           "16:9",
  "prompt":                 "Visual style: ...",
  "prompt_char_count":      1842,
  "reference_images_count": 2,
  "output_file":            "output/scene1_final_sprites_20250115_143210.mp4",
  "file_size_mb":           18.4,
  "video_duration_seconds": 29.0,
  "generation_time":        47.2,
  "retry_count":            0,
  "estimated_cost_usd":     11.6,
  "success":                true,
  "error":                  null,
  "error_type":             null,
  "eval_passed":            null,
  "eval_report_path":       null
}
```

`estimated_cost_usd` uses the Video+Audio pricing tier (Veo 3.1 models generate audio by default). Pricing source: Google Cloud pricing page.

### Per-clip-attempt entries (`--verify-clips` only)

Every generation attempt for a clip — pass or fail, first try or a retry — gets its own entry, in addition to the scene-level entries above:

```json
{
  "timestamp":              "2026-07-13T10:41:27.000000",
  "scene_id":               3,
  "clip_id":                2,
  "attempt_number":         1,
  "model":                  "veo-3.1",
  "model_api_name":         "veo-3.1-generate-preview",
  "resolution":             "720p",
  "aspect_ratio":           "16:9",
  "prompt":                 "This clip is a direct continuation...",
  "prompt_char_count":      612,
  "reference_images_count": null,
  "output_file":            "output/failed_clips/scene3_clip2_20260713_104127.mp4",
  "file_size_mb":           1.2,
  "video_duration_seconds": 7.0,
  "generation_time":        63.4,
  "retry_count":            null,
  "estimated_cost_usd":     2.8,
  "success":                false,
  "error":                  "dialogue mismatch (similarity=10.0)",
  "error_type":             "content_eval_failed",
  "eval_passed":            false,
  "eval_report_path":       "../Transcript_Eval_Pipeline/output/eval_reports/scene3_clip2_20260713_104127_eval.json"
}
```

`output_file` is `null` for a **passed** attempt (nothing kept — its content already lives on in the ongoing cumulative video); it points into `output/failed_clips/` for a **failed** one. `eval_report_path` always points to the full `transcript_eval` report for that attempt (dialogue-match + speaker-attribution detail), regardless of pass/fail.

`error_type` values: `transient`, `content_policy`, `quota`, `content_eval_failed` (a `--verify-clips` clip exhausted its retries), or `unknown`.

---

## Module reference

### `scenario_loader`

| Function | Description |
|----------|-------------|
| `load_scenario(json_path)` | Load and return the scenario dict; raises `ValueError` on missing required keys |
| `validate_scenario(scenario)` | Check that `scenes`, `characters`, and `visual_style` are present |

### `prompt_builder`

| Function | Description |
|----------|-------------|
| `build_character_block(characters)` | Build the appearance + role string for all characters |
| `build_dialogue_block(scene, char_lookup)` | Build the numbered dialogue list, or a silence instruction when there is none |
| `build_veo_prompt(scene, characters, visual_style, is_continuation)` | Assemble the full prompt; first clip gets full context, extension clips get a compressed continuation prompt |
| `build_clip_prompts(scene, characters, visual_style)` | Return one prompt per clip for the stitching pipeline |

### `veo_api`

| Function | Description |
|----------|-------------|
| `create_reference_image_configs(reference_images)` | Convert PNG paths to `VideoGenerationReferenceImage` objects |
| `generate_first_clip(client, prompt, ...)` | Generate the opening clip (4 / 6 / 8 s); reference images force 8 s; returns `(video_obj, attempts_used)` |
| `generate_extension_clip(client, prompt, previous_video_obj, clip_index)` | Extend the previous clip by ~7 s; returns `(video_obj, attempts_used)` |
| `poll_until_done(client, operation)` | Poll until the operation reaches a terminal state; raises on permanent or transient errors |
| `generate_with_retry(generate_fn, label)` | Wrap a generate+poll thunk with exponential-backoff retry; returns `(result, attempts_used)` |
| `download_video(client, video_obj, output_file)` | Download the current video object to disk (cumulative for extension clips) |
| `estimate_cost(model_key, resolution, duration_seconds)` | Return estimated USD cost for the generated video |
| `get_video_duration(path)` | Read actual playback duration from the saved MP4 via moviepy |
| `ClipEvalFailedError` | Raised by `pipeline` when a clip still fails `--verify-clips` eval after all retries; classified by `_classify_error` as `"content_eval_failed"` |

### `pipeline`

| Function | Description |
|----------|-------------|
| `run_scene_pipeline(client, scene_id, clip_prompts, ..., verify_clips=False, eval_retries=1, scene=None, characters=None)` | Generate one scene as a stitched multi-clip video; saves a checkpoint on partial failure; optionally verifies + regenerates each clip |
| `run_scenario_pipeline(client, scenario, reference_images, verify_clips=False, eval_retries=1)` | Iterate all scenes through the stitching pipeline; returns a list of `{scene_id, success, output_file, error}` dicts |
| `_generate_and_verify(generate_fn, clip_id, client, verify_clips, eval_retries, prev_duration, scene_id, dialogue, characters, prompt)` | Generate one clip, verify + retry on failure if `verify_clips`, logging every attempt via `_log_clip_attempt`; returns `(video_obj, attempts, new_duration)` or raises `ClipEvalFailedError` |
| `_log_clip_attempt(scene_id, clip_id, attempt_number, prompt, report, video_path, attempt_wall_time)` | Write one `generation_log.json` entry for a single clip-generation attempt (pass or fail) |

### `clip_verification`

| Function | Description |
|----------|-------------|
| `extract_new_segment(cumulative_video_path, prev_duration, new_duration, out_path)` | Trim `[prev_duration, new_duration)` out of a cumulative Veo download to isolate the newest clip |
| `verify_clip(client, video_obj, prev_duration, scene_id, clip_id, dialogue, characters, tmp_dir)` | Download → isolate → `transcript_eval.evaluate_clip()`; always deletes the cumulative download, deletes the isolated clip too only if eval passed; returns `(report, new_cumulative_duration, kept_clip_path_or_None)` — the path is only non-`None` on failure |
| `eval_report_path_for(video_path)` | Derive the `transcript_eval` eval-report path for a given clip video path (same stem, `Transcript_Eval_Pipeline/output/eval_reports/` dir) — used to link a `generation_log.json` entry to its full eval report |
| `eval_failure_reason(report)` | One-line human-readable reason an eval report failed, for log/print messages |

### `logging_utils`

| Function | Description |
|----------|-------------|
| `load_log()` | Return the existing `generation_log.json` entries, or `[]` |
| `save_log(entries)` | Write the log list back to disk |
| `save_prompt(prompt, output_file)` | Write the prompt text to a `.txt` file next to the output video |
| `log_generation(scene_id, model_key, prompt, output_file, ..., clip_id=None, attempt_number=None, eval_passed=None, eval_report_path=None)` | Append one generation result to the log; returns the entry dict. The last four kwargs are only populated for `--verify-clips` per-attempt entries |
| `save_checkpoint_metadata(scene_id, clip_index, checkpoint_file, error)` | Append a checkpoint record to the log when a stitch run fails partway |

### `cli`

| Function | Description |
|----------|-------------|
| `load_env()` | Read `.env` from the working directory and export key=value pairs |
| `init_output_dir()` | Create `output/` if it does not exist |
| `parse_args()` | Build and parse the CLI argument parser |
| `burn_captions(video_path, dialogue, characters, ...)` | Overlay dialogue as timed text clips using `moviepy` |
| `main()` | Entry point: load env → parse args → load scenario → run pipeline → print summary |

---

## Testing prompts without API calls

```bash
# Print per-clip prompts for all scenes
python test_prompt.py

# Print per-clip prompts for one scene via CLI
python -m video_generator.cli --scenario scenario.json --scene-id 3 --preview-prompt
```

No Veo API calls are made in either case.
