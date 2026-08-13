# Local video generation (Wan 2.2 on ComfyUI)

This pipeline turns a scenario script into character video. It runs entirely on
one machine's GPU using Wan 2.2 through ComfyUI, so a full scenario costs
nothing to render and needs no API key. There is also an older Google Veo path,
kept only so old runs stay reproducible; everything new should use the local
backend.

The other half of the video system is the Manim diagram generator, documented in
[`manim_generator/README.md`](manim_generator/README.md). The two are
independent: Manim draws explanatory diagrams, this pipeline renders people.

A third technique, [`solo_clip/`](solo_clip/README.md), renders each dialogue line
as its own isolated Veo clip with one character alone in frame and stitches them
afterward. It costs money because it runs on Veo, but it makes the
wrong-speaker-in-frame artifact impossible rather than something to prompt around.
Nothing here depends on it.

<!-- VIDEO: drop a rendered scene mp4 here.
     On GitHub, edit this file in the browser and drag the file into the editor.
     GitHub uploads it and leaves a https://github.com/user-attachments/... link
     that plays inline. Keep clips under 10MB so they load quickly. -->

## What it produces

Input is a scenario JSON with scenes, characters, and per-scene clips. Output is
one mp4 per scene, plus a JSON log of every clip that was generated.

Each scene is rendered as a series of 5 second clips which are then concatenated
with ffmpeg. Clips exist because each generation job produces 81 frames, which is
5 seconds at 16 fps. A 20 second scene is four clips stitched end to end, not one
long generation. Longer jobs are possible but VRAM and coherence both fall off
fast, and 81 frames is where this setup was stable.

## What it actually cost and how long it took

These are the real numbers from `output/generation_log.json`, covering the runs
behind the demo:

| | |
|---|---|
| Scene runs logged | 46 |
| Scene runs that succeeded | 30 |
| Individual clips generated | 84 |
| Time per 5 second clip | 255s min, 332s median, 437s max |
| Time per scene, end to end | 11.5 min median, 23 min worst case |
| Finished video produced | 424 seconds |
| Total GPU cost | $0.00 |

The 16 failed runs were all one bug, a call passing a `default_setting` argument
that `build_clip_prompts` did not accept. That is fixed. None of the failures
were the model producing unusable video.

The practical takeaway for planning: on a single RTX 3090, budget roughly 5 to 6
minutes of wall clock per 5 seconds of finished video. An 8 scene scenario is a
90 minute to 2 hour job. This is the main reason the API runs generation as a
background task and reports progress by polling rather than blocking.

## Hardware and software you need

Tested on an RTX 3090 with 24GB VRAM, Ubuntu, Python 3.12. The Q6_K quantized
models were chosen specifically to fit two 14B models in 24GB; on a smaller card
you will need a lower quantization, and on a larger card you can move up.

ComfyUI must be running and reachable before you start:

```bash
cd ~/comfyui && python main.py --listen 127.0.0.1 --port 8188
```

The pipeline talks to it over plain HTTP at `http://127.0.0.1:8188`. It does not
import ComfyUI or share a process with it, which means you can restart either
side independently.

### Model files

All of these go under `~/comfyui/models/`. The pipeline checks that every one of
them exists on disk before it submits anything, so a missing file fails in two
seconds instead of after a five minute render.

```
diffusion_models/Wan2.2-T2V-A14B-HighNoise-Q6_K.gguf
diffusion_models/Wan2.2-T2V-A14B-LowNoise-Q6_K.gguf
diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q6_K.gguf
diffusion_models/Wan2.2-I2V-A14B-LowNoise-Q6_K.gguf
loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors
loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors
loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors
loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors
text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
vae/wan_2.1_vae.safetensors
```

If ComfyUI lives somewhere else, set `COMFY_ROOT`. If it listens elsewhere, set
`COMFY_API`. Both are read from the environment at import time.

## Running it

```bash
cd BackEnd/Video_Generation_Pipeline

# Validate everything without generating. Builds each clip's payload, resolves
# every node reference, checks every model file against disk, and asks the live
# server whether it knows each node type. Submits nothing.
python -m video_generator.cli --scenario scenario.json --scene-id 1 --dry-run

# One scene, text to video
python -m video_generator.cli --scenario scenario.json --scene-id 3

# Every scene
python -m video_generator.cli --scenario scenario.json

# Image to video. Clip 1 starts from the given image, and every clip after that
# starts from the previous clip's last frame.
python -m video_generator.cli --scenario scenario.json --scene-id 3 \
    --i2v-start-image reference_images/maya.png

# Image to video with a character LoRA pinned on the low noise branch
python -m video_generator.cli --scenario scenario.json --scene-id 3 \
    --i2v-start-image reference_images/maya.png \
    --character-lora mayanurse_low.safetensors

# See the prompts without generating anything
python -m video_generator.cli --scenario scenario.json --scene-id 3 --preview-prompt
```

Run `--dry-run` first on any machine you have not generated on before. It catches
a wrong `COMFY_ROOT`, a missing model file, and a ComfyUI install without the
GGUF custom nodes, which are the three things that actually go wrong.

Per-clip mp4s land under `~/comfyui/output/wan22/`. The stitched per-scene video
lands in `output/scene{N}_final_local_{timestamp}.mp4`.

Offline tests, no GPU and no job submission:

```bash
../venv/bin/python -m unittest discover -s tests
```

28 tests, about 1 second.

## CLI flags

| Flag | Applies to | What it does |
|---|---|---|
| `--scenario` | both | Path to the scenario JSON. Required. |
| `--scene-id` | both | Render one scene. Omit for all scenes. |
| `--model` | both | `local` (default) or `veo-3.1`, `veo-3.1-fast`, `veo-3.1-lite`, `veo-2`. |
| `--dry-run` | local | Build, print, and validate every payload. Submit nothing. |
| `--i2v-start-image` | local | Start image. Switches T2V to I2V. |
| `--character-lora` | local | LoRA filename in `models/loras`, applied to the low noise branch. |
| `--seed` | local | Sampler seed. Default 30003. |
| `--preview-prompt` | both | Print prompts, skip generation. |
| `--add-captions` | both | Burn dialogue captions onto the output. Needs moviepy. |
| `--verify-clips` | veo | Judge each clip as it is generated and regenerate on failure. |
| `--eval-retries` | veo | Regeneration attempts per failed clip. Default 1. |
| `--api-key` | veo | Gemini key. Defaults to `$GEMINI_API_KEY`. |

## How the workflow is built

`local_api.build_workflow()` constructs a ComfyUI API graph as a plain Python
dict, one per clip. There is no saved workflow JSON to keep in sync; the graph
is built in code so the model choice, resolution, seed, and LoRA stack are all
determined by function arguments.

The node layout mirrors the reference `wan22_i2v_api.json` workflow that was
validated by hand before any of this was automated:

| Node | Type | Role |
|---|---|---|
| 1, 2 | `UnetLoaderGGUF` | Wan 2.2 A14B high noise and low noise GGUF |
| 3, 4 | `LoraLoaderModelOnly` | lightx2v 4 step distill LoRAs, one per branch |
| 5, 6 | `ModelSamplingSD3` | shift 5.0 |
| 7 | `CLIPLoader` | umt5_xxl text encoder |
| 8 | `VAELoader` | wan_2.1_vae |
| 9, 10 | `CLIPTextEncode` | positive prompt and negative prompt |
| 11, 17 | `WanImageToVideo`, `LoadImage` | I2V only |
| 11 | `EmptyHunyuanLatentVideo` | T2V only |
| 12, 13 | `KSamplerAdvanced` | two stage sampling, see below |
| 14 | `VAEDecode` | latents to frames |
| 15 | `CreateVideo` | 16 fps |
| 16 | `SaveVideo` | h264 mp4 |
| 18 | `LoraLoaderModelOnly` | optional character LoRA, low noise branch only |

### Why two samplers

Wan 2.2 A14B ships as two separate 14B models rather than one. The high noise
model handles the early denoising steps where composition and motion are decided,
and the low noise model handles the later steps where detail resolves. Node 12
runs steps 0 to 4 on the high noise model and hands the partially denoised latent
to node 13, which runs steps 4 to 8 on the low noise model.

Eight total steps is unusually low for a diffusion model. That is what the
lightx2v 4 step distill LoRAs buy: they compress what would normally take 20 to
40 steps into 4 per branch. They also require `cfg 1.0`, which disables
classifier free guidance. This is why the negative prompt has less influence here
than it would in a normal Stable Diffusion workflow, and why prompt engineering
on the positive side matters more.

The character LoRA at node 18 is deliberately applied to the low noise branch
only. Identity is a detail level property, so pinning it late keeps a face
consistent without the LoRA fighting the high noise model over composition and
motion.

### Defaults

All of these are constants at the top of `local_api.py`.

| Constant | Value | Note |
|---|---|---|
| `DEFAULT_WIDTH` x `DEFAULT_HEIGHT` | 832 x 480 | One of the two resolutions A14B supports. The other is 720p. |
| `DEFAULT_LENGTH` | 81 frames | About 5 seconds at 16 fps |
| `DEFAULT_FPS` | 16 | Native rate. Interpolate afterward if you want 30. |
| `DEFAULT_STEPS` | 8 | 4 high noise, 4 low noise |
| `BOUNDARY_STEP` | 4 | Where the high noise model hands off |
| `DEFAULT_CFG` | 1.0 | Required by the distill LoRAs |
| `DEFAULT_SHIFT` | 5.0 | ModelSamplingSD3 |
| `DEFAULT_SEED` | 30003 | Fixed so runs are reproducible |
| `POLL_INTERVAL_SECONDS` | 15 | How often `/history` is checked |
| `GENERATION_TIMEOUT_SECONDS` | 3600 | Per clip ceiling |

Raising the resolution is the most expensive knob. Wan 2.2 A14B also supports
720p, but at these clip lengths it roughly doubles generation time on a 3090 and
in testing did not improve motion enough to justify that. Rendering at 480p and
upscaling afterward was the better trade for this project. If you have more GPU
than we did, this is the first setting worth revisiting.

## Character consistency

This was the hardest problem in the whole pipeline and it is worth understanding
before extending anything.

Text to video gives you no control over what a character looks like from clip to
clip. Three mechanisms address that, in increasing order of strength:

1. **Appearance text in the prompt.** `prompt_builder.build_character_block()`
   writes each character's skin tone, hair, build, and uniform into every clip
   prompt. Cheap, and it gets you in the neighborhood.
2. **Image to video chaining.** With `--i2v-start-image`, clip 1 starts from a
   real image. Every clip after that starts from the previous clip's last frame,
   extracted with ffmpeg by `extract_last_frame()`. This is what actually holds a
   character together across a scene. It is also why the API path always uses
   i2v: the approved opening frame from the image pipeline becomes the start
   image, so video generation inherits a character the user already signed off on.
3. **A character LoRA.** Strongest and most work. Train a LoRA on the character,
   drop it in `models/loras`, pass `--character-lora`. Used for the Maya
   character in the demo.

Chaining has a real failure mode. Each clip inherits the last frame of the one
before it, so errors compound: if clip 2 drifts, clips 3 and 4 drift further from
the same starting point. In practice scenes longer than about 4 clips start
showing visible drift, which is the main reason scenes are kept short.

## Output and logging

```
output/
  scene{N}_final_local_{timestamp}.mp4   stitched scene video
  generation_log.json                    every scene run, every clip
  demo/                                  demo videos kept for reference
~/comfyui/output/wan22/
  scene{N}_clip{K}_*.mp4                 individual clips before stitching
```

`generation_log.json` is a list of scene attempts. Each carries the model key,
success flag, wall time, output path, file size, and a `clips` array with one
entry per clip including its full prompt and generation time. Cost is recorded as
`0.0` on the local path, which is the point. The Veo entries in the same file
carry real dollar figures, so the two are directly comparable.

## How the API uses this

The FastAPI backend wraps the pipeline in `BackEnd/API/instructor_api_helpers.py`.

```
POST /instructor_api/generate_videos   {script, request_id, background_image_path,
                                        character_image_file_mapping, backend,
                                        character_lora}
    -> {"status": "started", "backend": "local"}

GET  /instructor_api/video_status/{request_id}
    -> {state, completed_scenes, failed_scenes, error?}
       state: planning_clips | rendering | done | completed_with_errors | failed

GET  /instructor_api/video/{video_path}
    -> the mp4
```

`run_video_generation()` does two things in order. First it calls
`clip_planner.plan_scenario_clips()`, which uses Gemini to break each scene's
dialogue into clip sized chunks while validating that every original line is
reused verbatim and in order. Then it dispatches to the chosen backend.

Two things worth knowing if you are integrating:

- **Clip planning still calls Gemini even on the local backend.** The rendering
  is free, the planning is not. `GEMINI_API_KEY` is required for the API path
  regardless of `backend`. The CLI path skips planning entirely and uses the
  clips already present in the scenario JSON, so the CLI is genuinely keyless.
- **Status is a file, not memory.** The background job writes `status.json`
  after every scene, and the status endpoint is a plain file read. Restarting the
  API does not lose progress on a run already in flight, and nothing is held in
  process state.

`on_scene_complete` is called as each scene lands, which is what lets the
frontend populate scene cards during a 90 minute run instead of showing a spinner.

## Scenario JSON

The shape the pipeline expects:

```json
{
  "title": "string",
  "learning_goal": "string",
  "visual_style": "string, fed verbatim into every clip prompt",
  "characters": [
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
  ],
  "scenes": [
    {
      "scene_id": 1,
      "type": "narrative",
      "duration_seconds": 28,
      "setting": "Single-occupancy hospital room",
      "character_actions": "Maya enters from the left",
      "camera": {"angle": "Medium two-shot", "movement": "Static",
                 "lens_effect": "Slightly warm, neutral depth"},
      "audio": {"sound_effects": "Soft ambient hospital sounds",
                "ambience": "Quiet hospital room"},
      "clips": [
        {
          "clip_id": 1,
          "dialogue": [{"character_id": "nurse_maya", "line": "Good morning, Carl."}],
          "character_actions": "Maya enters from the left",
          "camera": {"angle": "Medium two-shot", "movement": "Static"}
        }
      ],
      "on_screen_text": null,
      "routes_to": {"type": "decision_point", "decision_point_id": 1}
    }
  ],
  "decision_points": [
    {
      "decision_point_id": 1,
      "question_text": "Carl says he's fine, but his arms are crossed.",
      "choices": [
        {"choice_id": "A", "text": "Name what you observed and ask directly.",
         "is_correct": true, "misconception": null, "routes_to_scene": 3},
        {"choice_id": "B", "text": "Reassure him that everything will be okay.",
         "is_correct": false,
         "misconception": "False reassurance is a nontherapeutic response.",
         "routes_to_scene": 2}
      ]
    }
  ]
}
```

Every scene needs a `clips` array. Each clip becomes one generation job.
`visual_style` is prepended to every prompt and is the single most effective lever
for keeping a scenario looking coherent, so it is worth spending time on.

`decision_points` drive branching in the player. This pipeline renders every scene
independently and ignores routing, which means scenes can be regenerated in any
order without invalidating the branch graph.

## Module reference

| File | What it holds |
|---|---|
| `local_api.py` | The local backend. Workflow construction, validation, submit, poll, ffmpeg concat, frame extraction. |
| `prompt_builder.py` | Scene and character data into per-clip prompt strings. |
| `clip_planner.py` | Gemini call that splits scene dialogue into clips, with verbatim-dialogue validation. |
| `scenario_loader.py` | Load and validate scenario JSON. |
| `logging_utils.py` | `generation_log.json`, prompt saving, checkpoints. |
| `cli.py` | Argument parsing, entry point, caption burning. |
| `pipeline.py` | Veo orchestration. Deprecated. |
| `../solo_clip/` | Sibling one-clip-per-speaker Veo technique. Independent, see its own README. |
| `veo_api.py` | Veo API calls, polling, retry, download. Deprecated. |
| `clip_verification.py` | Bridges to `Transcript_Eval_Pipeline` for `--verify-clips`. Veo only. |

Key functions in `local_api.py`:

| Function | What it does |
|---|---|
| `build_workflow(...)` | The ComfyUI node graph for one clip, t2v or i2v |
| `validate_workflow(...)` | Dangling node refs and missing model files |
| `check_server_node_types(...)` | Cross checks node types against the live `/object_info` |
| `submit_workflow(...)` | POST `/prompt`, returns a prompt id |
| `wait_for_completion(...)` | Polls `/history/<id>` to a terminal state |
| `generate_clip(...)` | Build, validate, submit, wait. Returns the clip mp4 path. |
| `extract_last_frame(...)` | ffmpeg last frame into ComfyUI `input/` for chaining |
| `concat_clips(...)` | Lossless ffmpeg concat |
| `run_scenario_pipeline_local(...)` | Whole scenario, with an `on_scene_complete` callback |

## Known limits

Worth being straight about these, since they shape what is realistic to build on
top.

**Speed.** 5 to 6 minutes per 5 seconds of video is the binding constraint on
everything. It rules out interactive iteration, which is why `--dry-run` and
`--preview-prompt` exist. Batching across multiple GPUs would be the obvious first
scaling move, and nothing in the design prevents it: each clip is an independent
ComfyUI job, so a queue in front of several ComfyUI instances would parallelize
cleanly.

**Drift over long scenes.** Chaining compounds errors past roughly 4 clips.
Scenes over 20 seconds are better split into separate scenes than generated as
one long chain.

**No audio.** Wan 2.2 generates silent video. The demo used Kokoro TTS on the
Manim side; the character video side has no voice track yet. Adding one means
generating TTS from the dialogue already in the scenario JSON and muxing it, which
is a contained piece of work.

**Lip sync.** There is none. The visual style guidance deliberately asks for mouth
movement that suggests speech rather than matching phonemes, because the model
cannot do the latter. If OpenStax wants real lip sync, that is a separate model,
not a parameter change here.

**Single machine.** `COMFY_ROOT` and `COMFY_API` are environment variables, so
pointing at a remote ComfyUI works, but there is no queue, no retry across hosts,
and no concurrency control. A second run against the same server will interleave
its jobs.

## The Veo backend, deprecated

Kept so old runs stay reproducible. Select with `--model veo-3.1`,
`veo-3.1-fast`, `veo-3.1-lite`, or `veo-2`. Requires `GEMINI_API_KEY`.

Veo works differently in a way that matters if you read the code. Its extension
API is cumulative: each call returns the entire video so far, not the new segment.
`clip_verification.py` exists to deal with that, trimming
`[prev_duration, new_duration)` out of each cumulative download so a single clip
can be judged in isolation by `Transcript_Eval_Pipeline`.

`--verify-clips` judges each clip against the script as it is generated and
regenerates on failure, so a bad clip is caught before further extension calls are
spent on top of it. It is opt in because it downloads the cumulative video after
every clip and adds a Gemini video judge call per clip.

Resolution, aspect ratio, and reference images are constants at the top of
`veo_api.py` rather than CLI flags. Failed attempts are kept under
`output/failed_clips/` with their eval reports so they can be inspected.

The reason the project moved off Veo is cost. The local backend produces
comparable quality for this use case at zero marginal cost, and the demo scenario
above cost $0.00 to render where Veo would have run into the hundreds.
