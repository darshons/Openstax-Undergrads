# transcript_eval

Judges a rendered Veo clip against its ground-truth `scenario.json` script using a single Gemini call over the clip's native video + audio — no separate transcription step, no per-segment frame sampling. Catches visual inconsistency (physically implausible motion), dialogue misattribution (wrong character's mouth moving), and script misalignment (spoken content diverging from the intended line), in one pass.

Operates **per clip**, not per stitched scene video: one clip video in, plus that clip's `dialogue[]` + the scene's `characters[]`/`setting`/`character_actions` (all read out of `scenario.json`) in, one eval report out. This package can be run standalone via its own CLI (below), and is also wired into `Video_Generation_Pipeline` via `--verify-clips` — see [`video_generator`'s README](../Video_Generation_Pipeline/README.md#clip-verification) for how generation calls into this package to verify (and regenerate) clips as they're produced.

---

## Module structure

```
transcript_eval/
  scenario_loader.py   — load scenario JSON, look up one clip's dialogue + characters + setting/actions
  video_judge.py        — the judge: uploads the clip to Gemini, asks for visual/dialogue/script-alignment issues, aggregates the report
  report_utils.py       — shared output-dir constant + report writer
  cli.py                 — argument parsing, entry point

output/
  eval_reports/           — one JSON per clip: full eval report (created on first run)

test_clips/               — sample single-clip videos for manual/smoke testing (gitignored contents; not eval input/output)
```

---

## Quick start

```bash
cd backend/Transcript_Eval_Pipeline
export GEMINI_API_KEY=your-key-here

python -m transcript_eval.cli \
  --video test_clips/scene3_clip1.mp4 \
  --scenario ../Video_Generation_Pipeline/scenario.json \
  --scene-id 3 \
  --clip-id 1
```

Prints a pass/fail summary and writes `output/eval_reports/<clip_video_stem>_eval.json` — the full eval report.

This path is anchored to this package's own directory (`Path(__file__).resolve().parent.parent`), not the caller's working directory — so `--verify-clips` calls from `Video_Generation_Pipeline` (run from *its* own directory) still land here, not in `Video_Generation_Pipeline/output/`.

The input `--video` must be a single clip's video (not a multi-clip stitched scene) — see [Why per-clip](#why-per-clip).

---

## Setup

Depends on `moviepy` (to read clip duration for cost estimation) and `google-genai`, both listed in `backend/backend_requirement.txt`.

The only API call is Gemini (`gemini-3.6-flash`), via the existing `GEMINI_API_KEY`. There's no local model or free stage — every judged clip costs an upload + one `generate_content` call.

---

## Why per-clip

Veo generates one scene as a chain of extension clips (see `Video_Generation_Pipeline`), and each clip has its own short `dialogue[]` (typically 1–3 lines, ~7–8 s). Evaluating at clip granularity — rather than the final stitched scene video — means:

- A clip's video duration is unambiguous (no need to compute where a clip's audio starts/ends inside a longer stitched video).
- A bad clip can be caught and regenerated before the pipeline spends further Veo extension calls building on top of it — this is exactly what `Video_Generation_Pipeline`'s `--verify-clips` flag does, isolating each new clip's segment out of Veo's cumulative video download before calling `evaluate_clip()` here (see [its README](../Video_Generation_Pipeline/README.md#clip-verification)).

---

## How the judge works (`video_judge.py`)

```
cli.main()
  └─ video_judge.evaluate_clip()
       └─ video_judge.judge_video()
            ├─ upload the clip to Gemini Files API, poll until processing finishes
            └─ one generate_content call: video + audio + prompt → structured JSON verdict
```

1. **Upload**: the clip is uploaded via `client.files.upload()` and polled until it leaves `PROCESSING` (Gemini processes video asynchronously).
2. **Single judged call**: the uploaded video (native video+audio, not sampled frames) plus a prompt describing the scene's characters, expected setting/actions, and expected dialogue (in order) are sent to Gemini in one `generate_content` call, with a Pydantic response schema (`_VideoJudgment`) enforcing structured output.
3. **Three checks, in order of importance**, each returning `<x>_issues_found: bool` + a one-sentence `<x>_notes`:
   - **Visual consistency** — flags only physically-impossible or logically-incoherent motion (objects clipping/floating, anatomically impossible movement, a character teleporting between frames). Deviating from the expected setting/actions in a plausible way is *not* flagged.
   - **Dialogue consistency** — for each expected line, is the right character's mouth moving (and no one else's)? Minor audio/lip-sync drift is not flagged; only a wrong-speaker or multiple-speakers-at-once case is.
   - **Script alignment** — does the spoken dialogue achieve what the script intends, allowing for paraphrasing? Least important of the three — only a clear mismatch counts.
4. **Pass/fail gate**: the clip **fails** only if the judge reports `confidence: "high"` *and* either a visual or dialogue issue. A script-alignment mismatch alone never fails a clip, and any `confidence: "low"` verdict passes regardless of what else was flagged.
5. **Cost estimate**: `estimate_video_judge_cost(duration_seconds)` — Gemini's documented ~263 combined video+audio tokens/sec at default resolution, plus a fixed ~300-token prompt overhead, priced at `gemini-3.6-flash` input rates.

### Report shape

`evaluate_clip()` writes `output/eval_reports/<clip_video_stem>_eval.json`:

```json
{
  "timestamp": "2026-08-05T10:15:00.000000",
  "scene_id": 3,
  "clip_id": 1,
  "video_path": "path/to/scene3_clip1.mp4",
  "video_judge": {
    "visual_issues_found": false,
    "visual_notes": "...",
    "dialogue_issues_found": false,
    "dialogue_notes": "...",
    "script_alignment_issues_found": false,
    "script_alignment_notes": "...",
    "confidence": "high",
    "status": "pass",
    "estimated_cost_usd": 0.0006
  },
  "estimated_cost_usd": 0.0006,
  "passed": true
}
```

If the model response can't be parsed into the expected schema, `judge_video()` returns a low-confidence pass rather than erroring the clip out.

---

## CLI flags

| Flag | Description |
|------|--------------|
| `--video` *(required)* | Path to the clip's video file |
| `--scenario` *(required)* | Path to `scenario.json` |
| `--scene-id` *(required)* | `scene_id` in `scenario.json` |
| `--clip-id` *(required)* | `clip_id` within that scene |
| `--api-key` | Gemini API key for the video judge (default: `$GEMINI_API_KEY`) |

---

## Module reference

### `scenario_loader`

| Function | Description |
|----------|--------------|
| `load_scenario(json_path)` | Load and return the scenario dict; raises `ValueError` on missing required keys |
| `validate_scenario(scenario)` | Check that `scenes` and `characters` are present |
| `get_clip(scenario, scene_id, clip_id)` | Return `{dialogue, characters, setting, character_actions}` for one clip (clip-level `character_actions` falls back to scene-level when absent) |

### `video_judge`

| Function | Description |
|----------|--------------|
| `estimate_video_judge_cost(duration_seconds)` | Estimated USD cost for judging a clip of the given duration |
| `judge_video(client, video_path, dialogue, characters, setting, character_actions)` | Upload the clip and run the single judged Gemini call; returns the `video_judge` dict shown above |
| `evaluate_clip(client, video_path, scene_id, clip_id, dialogue, characters, setting, character_actions)` | Run `judge_video()`, wrap it in the full report shape, save it via `report_utils.save_eval_report`, and return it |

### `report_utils`

| Function | Description |
|----------|--------------|
| `save_eval_report(video_path, report)` | Write the report to `output/eval_reports/<stem>_eval.json` |
| `EVAL_REPORT_DIR` | Default output dir, anchored to this package's location regardless of caller's CWD |

### `cli`

| Function | Description |
|----------|--------------|
| `load_env()` | Read `.env` from the working directory and export key=value pairs |
| `parse_args()` | Build and parse the CLI argument parser |
| `main()` | Entry point: load env → parse args → look up clip → run eval → print summary |

---

## Scope

This package is usable two ways:
- **Standalone**, via `transcript_eval.cli` (above) — point it at any clip video + `scenario.json` + scene/clip IDs.
- **Integrated**, via `Video_Generation_Pipeline`'s `--verify-clips` flag, which calls `video_judge.evaluate_clip()` directly (through `video_generator/clip_verification.py`) after isolating each newly generated clip from Veo's cumulative video — see [its README](../Video_Generation_Pipeline/README.md#clip-verification) for the full mechanism, including the retry-on-failure behavior.

**Not** implemented here:
- Any UI surface for eval reports — today's output is JSON files under `output/eval_reports/`.
