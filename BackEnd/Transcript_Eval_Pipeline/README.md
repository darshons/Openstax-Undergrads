# transcript_eval

Generates a transcript from a rendered Veo clip — independent of anything the video generator knew about its own script — then evaluates that transcript against the clip's ground-truth `scenario.json` dialogue. Catches two failure modes Veo can introduce: wrong/garbled spoken dialogue, and dialogue delivered by the wrong character on screen.

Operates **per clip**, not per stitched scene video: one clip video in, plus that clip's `dialogue[]` + the scene's `characters[]` (both read out of `scenario.json`) in, one eval report out. This package can be run standalone via its own CLI (below), and is also wired into `Video_Generation_Pipeline` via `--verify-clips` — see [`video_generator`'s README](../Video_Generation_Pipeline/README.md#clip-verification) for how generation calls into this package to verify (and regenerate) clips as they're produced.

---

## Module structure

```
transcript_eval/
  scenario_loader.py   — load scenario JSON, look up one clip's dialogue + characters
  transcribe.py         — Stage 1: audio extraction + local Whisper ASR
  match_dialogue.py     — Stage 2: deterministic fuzzy match vs. scenario.json, early-stop gate
  judge_speaker.py       — Stage 3: frame sampling + vision LLM speaker-attribution judge
  eval.py                 — orchestrates stages 1→2→3, aggregates the report
  cli.py                  — argument parsing, entry point

output/
  transcripts/            — one JSON per clip: raw Whisper segments (created on first run)
  eval_reports/            — one JSON per clip: full eval report (created on first run)

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

Prints a pass/fail summary and writes:
- `output/transcripts/<clip_video_stem>.json` — the raw Whisper transcript
- `output/eval_reports/<clip_video_stem>_eval.json` — the full eval report

These paths are anchored to this package's own directory (`Path(__file__).resolve().parent.parent`), not the caller's working directory — so `--verify-clips` calls from `Video_Generation_Pipeline` (run from *its* own directory) still land here, not in `Video_Generation_Pipeline/output/`.

The input `--video` must be a single clip's video (not a multi-clip stitched scene) — see [Why per-clip](#why-per-clip).

---

## Setup

Depends on `moviepy`, `openai-whisper`, `rapidfuzz`, `pillow`, and `google-genai` — all listed in `backend/backend_requirement.txt`.

`openai-whisper` runs entirely locally (no API key, no per-call cost) but shells out to an `ffmpeg` binary on `PATH`. `moviepy` bundles its own ffmpeg via `imageio-ffmpeg`, but under a platform-suffixed filename `whisper` won't find directly — `transcribe.py` handles this automatically by symlinking it to a plain `ffmpeg` name in a temp directory and prepending that to `PATH` at runtime. No manual ffmpeg install is required.

The first `transcribe_clip()` call downloads the Whisper `base` model (~140 MB) to `~/.cache/whisper` and caches it for subsequent runs.

Only Stage 3 (`judge_speaker.py`) calls a paid API — Gemini, via the existing `GEMINI_API_KEY`. Stage 1 and Stage 2 are free.

---

## Why per-clip

Veo generates one scene as a chain of extension clips (see `Video_Generation_Pipeline`), and each clip has its own short `dialogue[]` (typically 1–3 lines, ~7–8 s). Evaluating at clip granularity — rather than the final stitched scene video — means:

- A clip's video duration is unambiguous (no need to compute where a clip's audio starts/ends inside a longer stitched video).
- A bad clip can be caught and regenerated before the pipeline spends further Veo extension calls building on top of it — this is exactly what `Video_Generation_Pipeline`'s `--verify-clips` flag does, isolating each new clip's segment out of Veo's cumulative video download before calling `evaluate_clip()` here (see [its README](../Video_Generation_Pipeline/README.md#clip-verification)).

---

## Pipeline stages

```
cli.main()
  └─ eval.evaluate_clip()
       ├─ transcribe.transcribe_clip()        ← Stage 1: Whisper ASR on the clip's audio
       ├─ match_dialogue.match_dialogue()     ← Stage 2: fuzzy match, clip-level, loose threshold
       │    └─ FAIL → early stop, Stage 3 skipped, clip marked failed
       └─ judge_speaker.judge_speakers()      ← Stage 3: only runs if Stage 2 passed
            └─ per-Whisper-segment frame sampling + Gemini vision judge
```

### Stage 1 — Transcription (`transcribe.py`)

Extracts audio from the clip with `moviepy`, runs it through local Whisper, and returns timestamped segments relative to the clip's own timeline:

```json
[{ "start": 0.0, "end": 7.0, "text": "I noticed you crossed your arms..." }]
```

This is the transcript — generated purely from what the video actually contains, with no knowledge of the intended script.

### Stage 2 — Deterministic dialogue match (`match_dialogue.py`)

Veo doesn't respect line boundaries — a script line can come out split across two Whisper segments, or two lines can blend into one. So this stage compares the **whole clip as one block** rather than line-by-line:

1. Concatenate the clip's expected `dialogue[]` lines from `scenario.json`.
2. Concatenate all of the clip's Whisper segments (Stage 1 output).
3. Score similarity with `rapidfuzz.fuzz.token_sort_ratio` against a **loose threshold** (`SIMILARITY_THRESHOLD = 75`) — loose on purpose, since this stage exists to catch obviously wrong/garbled/missing dialogue, not to penalize paraphrasing.

If it fails, the clip is marked failed and **Stage 3 is skipped** — no vision-judge API cost is spent verifying speaker attribution for dialogue that's already wrong.

### Stage 3 — Speaker attribution judge (`judge_speaker.py`)

Only runs if Stage 2 passed. Uses Stage 1's original per-segment timestamps directly (not the Stage 2 concatenation):

1. For each Whisper segment, sample 4 evenly-spaced frames across `[start, end]`.
2. Send the frames + the scene's character list (name, appearance) to Gemini (`gemini-2.5-flash`), asking which character(s) appear to be speaking based on lip movement, gesture, and body orientation.
3. Collapse consecutive same-speaker judgments (so a line split across multiple segments doesn't artificially break the sequence), and compare the resulting speaker sequence to the expected order from the clip's `dialogue[]`.

**Both-speaking / ambiguous frames**: the judge is asked for a *list* of speaking characters per segment, not a single forced answer, precisely because a reaction shot (or genuinely overlapping dialogue) can show both characters' mouths moving at once. A segment is only used as a clean signal in the sequence comparison when exactly one character is reported:

| `speaking_characters` result | `judged_speaker` | Counted as |
|---|---|---|
| exactly one character | that character | a normal data point in the sequence |
| two or more characters | `null` | `ambiguous` — excluded from the sequence, tallied in `ambiguous_segments` |
| none / unparseable | `null` | `inconclusive` — excluded from the sequence, tallied in `inconclusive_segments` |

Excluded segments never get silently guessed into the sequence — if a clip has too many ambiguous/inconclusive segments to draw a reliable conclusion from, that's visible directly in the report (`ambiguous_segments` / `inconclusive_segments` counts) rather than the clip quietly passing or failing on a coin-flip guess.

Tracks estimated cost via `estimate_judge_cost()` (Gemini 2.5 Flash input-token pricing: ~258 tokens/image × 4 frames + prompt overhead, per segment judged).

### Aggregation (`eval.py`)

Combines both stages into one report and writes it to `output/eval_reports/<clip_video_stem>_eval.json`:

```json
{
  "timestamp": "2026-07-08T10:15:00.000000",
  "scene_id": 3,
  "clip_id": 1,
  "video_path": "path/to/scene3_clip1.mp4",
  "transcript_path": "output/transcripts/scene3_clip1.json",
  "dialogue_match": {
    "expected_text": "Carl, I noticed you crossed your arms...",
    "transcribed_text": "I noticed you crossed your arms...",
    "similarity": 73.7,
    "passed": true
  },
  "speaker_attribution": {
    "segments": [
      {
        "start": 0.0,
        "end": 7.0,
        "candidates": ["nurse_maya"],
        "judged_speaker": "nurse_maya",
        "ambiguous": false,
        "rationale": "..."
      }
    ],
    "expected_speaker_order": ["nurse_maya"],
    "ambiguous_segments": 0,
    "inconclusive_segments": 0,
    "attribution_passed": true,
    "estimated_cost_usd": 0.0004
  },
  "speaker_attribution_skipped_reason": null,
  "estimated_cost_usd": 0.0004,
  "passed": true
}
```

If Stage 2 failed, `speaker_attribution` is `null` and `speaker_attribution_skipped_reason` explains why.

---

## CLI flags

| Flag | Description |
|------|--------------|
| `--video` *(required)* | Path to the clip's video file |
| `--scenario` *(required)* | Path to `scenario.json` |
| `--scene-id` *(required)* | `scene_id` in `scenario.json` |
| `--clip-id` *(required)* | `clip_id` within that scene |
| `--api-key` | Gemini API key for the Stage 3 judge (default: `$GEMINI_API_KEY`) |

---

## Module reference

### `scenario_loader`

| Function | Description |
|----------|--------------|
| `load_scenario(json_path)` | Load and return the scenario dict; raises `ValueError` on missing required keys |
| `validate_scenario(scenario)` | Check that `scenes` and `characters` are present |
| `get_clip(scenario, scene_id, clip_id)` | Return `{dialogue, characters}` for one clip |

### `transcribe`

| Function | Description |
|----------|--------------|
| `extract_audio(video_path, audio_path)` | Extract the clip's audio track to a `.wav` file via moviepy |
| `transcribe_clip(video_path)` | Run local Whisper ASR; returns `[{start, end, text}, ...]` |
| `save_transcript(video_path, segments, output_dir)` | Write the segment list to `output/transcripts/<stem>.json` |

### `match_dialogue`

| Function | Description |
|----------|--------------|
| `match_dialogue(dialogue, segments)` | Concatenate + fuzzy-compare expected vs. transcribed text; returns `{expected_text, transcribed_text, similarity, passed}` |

### `judge_speaker`

| Function | Description |
|----------|--------------|
| `sample_frames(video_path, start, end, count)` | Return `count` evenly-spaced JPEG frame bytes from `[start, end]` |
| `judge_segment_speaker(client, video_path, start, end, characters)` | Ask Gemini vision who is speaking in one segment; returns `candidates`/`judged_speaker`/`ambiguous` (see [both-speaking handling](#stage-3--speaker-attribution-judge-judge_speakerpy)) |
| `judge_speakers(client, video_path, segments, dialogue, characters)` | Judge every segment, compare the collapsed speaker sequence to the expected order, tally `ambiguous_segments`/`inconclusive_segments` |
| `estimate_judge_cost(num_calls)` | Estimated USD cost for a given number of Stage 3 judge calls |

### `eval`

| Function | Description |
|----------|--------------|
| `evaluate_clip(client, video_path, scene_id, clip_id, dialogue, characters)` | Run all three stages and return the aggregated report dict |
| `save_eval_report(video_path, report)` | Write the report to `output/eval_reports/<stem>_eval.json` |
| `TRANSCRIPT_DIR`, `EVAL_REPORT_DIR` | Default output dirs, anchored to this package's location regardless of caller's CWD |

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
- **Integrated**, via `Video_Generation_Pipeline`'s `--verify-clips` flag, which calls `eval.evaluate_clip()` directly (through `video_generator/clip_verification.py`) after isolating each newly generated clip from Veo's cumulative video — see [its README](../Video_Generation_Pipeline/README.md#clip-verification) for the full mechanism, including the retry-on-failure behavior.

**Not** implemented here:
- Any UI surface for eval reports — today's output is JSON files under `output/eval_reports/`.
