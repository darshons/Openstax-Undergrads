# video_generator

Generates MP4 videos from a scenario JSON file using Google Veo. Each scene in the scenario becomes one video clip — or a chain of extension clips for longer scenes — produced by the Veo API and saved locally.

---

## Module structure

```
video_generator/
  scenario_loader.py   — load and validate the scenario JSON
  prompt_builder.py    — convert scene data into Veo prompt strings
  veo_api.py           — Veo API calls, polling, retry, and download
  pipeline.py          — scene and scenario orchestration
  logging_utils.py     — generation log, prompt saving, checkpoints
  cli.py               — argument parsing, entry point, caption burning
```

---

## Quick start

```bash
cd backend/Video_Generation_Pipeline
export GEMINI_API_KEY=your-key-here

# Generate one scene
python -m video_generator.cli --scenario scenario.json --scene-id 1

# Preview the prompt without generating
python -m video_generator.cli --scenario scenario.json --scene-id 1 --preview-prompt

# Generate all scenes with a specific model
python -m video_generator.cli --scenario scenario.json --model veo-3.1-fast

# Generate all scenes and burn captions
python -m video_generator.cli --scenario scenario.json --add-captions

# Run the same scene through every model (for comparison)
python -m video_generator.cli --scenario scenario.json --scene-id 1 --compare-models

# Pass reference images for character consistency (first clip only)
python -m video_generator.cli --scenario scenario.json --reference-images maya.png carl.png
```

Output videos are saved to `output/`. A generation log is written to `output/generation_log.json` after every run.

---

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--scenario` | *(required)* | Path to the scenario JSON file |
| `--scene-id` | all scenes | Generate only this scene ID |
| `--model` | `veo-3.1` | Model key: `veo-3.1`, `veo-3.1-fast`, `veo-3.1-lite`, `veo-2` |
| `--compare-models` | off | Run the same scene through all four models |
| `--resolution` | `720p` | `720p`, `1080p`, or `4k` |
| `--aspect-ratio` | `16:9` | `16:9` or `9:16` |
| `--reference-images` | none | Paths to up to 3 PNG reference images for character appearance pinning |
| `--prompt-override` | none | Use this string instead of the auto-built prompt |
| `--preview-prompt` | off | Print the generated prompt; skip API call |
| `--add-captions` | off | Burn dialogue captions onto the generated video (requires `moviepy`) |
| `--api-key` | `$GEMINI_API_KEY` | Gemini API key |

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

**`clips`** — optional array. When present, the scene is generated as a chain of Veo extension clips rather than a single generation. Each clip has its own `dialogue`, `character_actions`, and `camera` override:

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

`on_screen_text` is placed only on the final clip of the scene. All other clips suppress text overlays.

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

Decision points are used by the frontend for interactive branching; the video pipeline ignores them and generates all scenes independently.

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
| `build_veo_prompt(scene, characters, visual_style, is_continuation)` | Assemble the full Veo prompt; set `is_continuation=True` for extension clips |
| `build_clip_prompts(scene, characters, visual_style)` | Return one prompt per clip for the stitching pipeline |

### `veo_api`

| Function | Description |
|----------|-------------|
| `create_reference_image_configs(reference_images)` | Convert PNG paths to `VideoGenerationReferenceImage` objects |
| `generate_first_clip(client, prompt, ...)` | Generate the opening clip (4 / 6 / 8 s); reference images force 8 s |
| `generate_extension_clip(client, prompt, previous_video_obj, clip_index)` | Extend the previous clip by ~7 s |
| `poll_until_done(client, operation)` | Poll until the operation reaches a terminal state; raises on errors |
| `generate_with_retry(generate_fn, label)` | Wrap a generate+poll thunk with exponential-backoff retry for transient errors |
| `download_video(client, video_obj, output_file)` | Download the final combined video to disk |
| `generate_video(client, prompt, scene_id, ...)` | Single-scene generation with logging; returns a log entry dict |

**Constants** (override by editing `veo_api.py`):

| Name | Default | Description |
|------|---------|-------------|
| `MODEL` | `veo-3.1-generate-preview` | Model used by the stitching pipeline |
| `RESOLUTION` | `720p` | Resolution for stitching pipeline clips |
| `ASPECT_RATIO` | `16:9` | Aspect ratio for stitching pipeline clips |
| `MAX_CLIPS` | `21` | Hard ceiling on clips per scene (~148 s) |
| `EXTENSION_SECONDS` | `7` | Duration added by each extension hop |
| `EXTENSION_SETTLE_SECONDS` | `15` | Delay between consecutive extension calls |
| `MAX_GENERATION_RETRIES` | `4` | Max retry attempts on transient failures |

### `pipeline`

| Function | Description |
|----------|-------------|
| `run_scene_pipeline(client, scene_id, clip_prompts, ...)` | Generate one scene as a stitched multi-clip video; saves a checkpoint if an extension fails mid-way |
| `run_scenario_pipeline(client, scenario, model_key, ...)` | Iterate all scenes and call `generate_video` for each; returns a list of log entries |

### `logging_utils`

| Function | Description |
|----------|-------------|
| `load_log()` | Return the existing `generation_log.json` entries, or `[]` |
| `save_log(entries)` | Write the log list back to disk |
| `save_prompt(prompt, output_file)` | Write the prompt text to a `.txt` file next to the output video |
| `log_generation(scene_id, model_key, prompt, output_file, ...)` | Append one generation result to the log; returns the entry dict |
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

## Two generation paths

### Single-generation path (default)

Used when a scene has no `clips` array, or when calling `generate_video` directly.

```
cli.main()
  └─ pipeline.run_scenario_pipeline()
       └─ veo_api.generate_video()   ← one Veo call per scene
```

### Stitching path (multi-clip scenes)

Used when a scene has a `clips` array. Each clip is a separate Veo call; each call continues from the last frame of the previous one.

```
pipeline.run_scene_pipeline()
  ├─ veo_api.generate_first_clip()        ← clip 1 (4/6/8 s)
  ├─ veo_api.generate_extension_clip()    ← clip 2 (~7 s)
  ├─ veo_api.generate_extension_clip()    ← clip 3 (~7 s)
  └─ veo_api.download_video()             ← final combined video
```

If an extension fails, the last successful combined video is saved as a checkpoint (`scene{N}_checkpoint_clip{K}_{ts}.mp4`) so the completed hops are not lost.

---

## Testing prompts without API calls

```bash
python test_prompt.py
```

Prints the assembled prompt for every clip in every scene using the local `scenario.json`. No Veo API calls are made.
