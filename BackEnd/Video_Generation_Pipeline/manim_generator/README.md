# Manim Branching-Video Generator

Generates the **"Manim · Graphics"** video type for Scenario Studio: one narrated **diagram**
clip per scene of a branching scenario script (narrative / consequence / resolution). Each
scene becomes an educational graphic — a flowchart, labeled figure, graph, or relationship
diagram — with the scenario's content read as Kokoro TTS narration over it, plus a manifest
describing the decision-point branch graph.

> **Diagrams, not characters.** Manim renders people badly, so this pipeline deliberately
> produces diagrammatic visuals (3Blue1Brown-style), never avatars or acted-out scenes. The
> named characters are spoken *about* in narration; they are not drawn.

It consumes the **same script JSON** the LLM script pipeline already produces (top-level
`scenes[]` + `decision_points[]`; see `Script_Generation_Pipeline/_JSON_Templates/`).

## Pipeline

```
script.json
  └─ script_adapter      normalize + validate the branch graph
  └─ asset_kit           generate a frozen assets.py DIAGRAM style-kit (palette, grid,
                         build_background / title_card / caption / label / emphasis_box) ONCE,
                         render its AssetLineup test frame, critique it, freeze
  └─ per scene (serial):
       scene_planner      1 LLM call → beats + occupancy table + narration/voice table
       code_generator     → Manim VoiceoverScene code (imports the frozen assets.py)
       render + repair     manim -qh ; on failure → ScopeRefine (line→block→full) with
                           RITL-truncated logs + De-Hallucinator API-signature injection
       grid critic         6×6-grid layout critique (>=1 forced pass), re-render on fix
  └─ manifest.json       branch graph: scene→clip, choice→routing, golden_path
  └─ golden_path.mp4     stitched correct-answers-only preview
```

The "conglomerate" techniques (ScopeRefine, RITL log truncation, API-KB grounding,
occupancy-table critic, TTS pre-budgeting) come from a deep-research survey of the
LLM→Manim field; the render/repair/grid-critic core is ported from the
TheoremExplainAgent OpenStax fork.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r BackEnd/Video_Generation_Pipeline/manim_generator/requirements.txt
python -m manim_generator.api_kb          # build the Manim API KB for repair grounding
```

Kokoro TTS model files are required (not vendored). Point these at them:

```
KOKORO_MODEL_PATH=/abs/path/to/kokoro-v0_19.onnx
KOKORO_VOICES_PATH=/abs/path/to/voices.bin
GEMINI_API_KEY=...
```

For the **API server**, put those in `BackEnd/backend.env` (loaded by `main.py`).
For the **CLI**, any `.env` walking up from the working directory is read.

`manim` must resolve to this venv's install both for the API process and for the render
subprocesses — the pipeline invokes `sys.executable -m manim`, so activating the venv is
enough.

## CLI

```bash
PYTHONPATH=BackEnd/Video_Generation_Pipeline python -m manim_generator.cli \
  --script BackEnd/Script_Generation_Pipeline/_Script_Outputs/output_script_with_decision_points_anthropic_new.json \
  --out output/manim_runs --request-id demo --quality m
```

`--quality l` (480p) is much faster for iteration; `h` (1080p) for final. A full 8-scene
scenario is roughly 30–60 min (dominated by LLM calls + serial renders).

## API

- `POST /api/generate_manim_videos` `{script, request_id}` → `{status: "started", request_id}`
  (runs in a 1-worker executor; renders must be serial).
- `GET  /api/manim_video_status/{request_id}` → `{state, completed_scenes, failed_scenes, manifest?, error?}`
  (`state` = `queued | assets | scene_k_of_n | stitching | done | error`).
- `GET  /api/video/{path}` serves a generated mp4 (existing endpoint).

The frontend `VideoPage` polls the status endpoint every 5s and populates scene cards as
clips complete.

## Notes / gotchas

- **Serial rendering is mandatory** — parallel manim subprocesses deadlock.
- The **asset kit is a single point of failure**; it gets a generous retry budget and a
  parameterized fallback diagram kit so a bad LLM generation can't hard-block a run.
- The **grid critic only fires after a successful render**, so at least one pass is forced
  per scene to catch layout defects in first-try-clean scenes.
- `manim_api_kb.json` is gitignored and rebuilt from the installed manim; `load_kb()`
  builds it on demand if missing.
