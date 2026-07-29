# DJ YAM

<img width="1000" alt="Gemini_Generated_Image_qvr6tsqvr6tsqvr6" src="https://github.com/user-attachments/assets/5325fc1f-557d-4917-9051-340a62103fd8" />

# OpenStax Scenario Studio

An authoring tool that lets OpenStax content editors generate, review, and refine **interactive educational scenario scripts** grounded in real OpenStax textbook content — then turn them into **branching educational videos**. The demo centerpiece is the **Manim graphics pipeline**: every scene of a branching scenario becomes a narrated 3Blue1Brown-style diagram clip, stitched together with decision points.

Built by Team DJ YAM.

---

## What it does

1. **Pick a textbook section** from the sidebar (Biology 2e, Clinical Nursing, Anatomy & Physiology, and more).
2. **Describe a scenario** — e.g. *"A nursing student watches a patient's glucose metabolism in real time."*
3. **Choose a model** — Anthropic Claude, Google Gemini, or the **local** provider (Claude Code CLI — no API key needed).
4. **Generate** — the backend crawls the relevant OpenStax HTML, feeds it to the LLM, and returns a structured JSON script with scenes, characters, decision points, and a setting description.
5. **Edit inline** — scene cards, character cards, and a setting panel are all editable in the browser. Decision-point branches are shown as an interactive tree; click a choice pill to mark it as the correct answer.
6. **Generate videos** — kick off the Manim branching-video pipeline straight from the UI, or export the script JSON for the other pipelines.

---

## Project structure

```
.
├── frontend/                        # React 19 + Vite + Tailwind UI (TypeScript)
│   └── src/
│
├── BackEnd/                         # FastAPI backend
│   ├── main.py                      # App entry point + CORS config
│   ├── api.py                       # All /api/* route handlers
│   ├── backend_requirement.txt      # Backend Python dependencies
│   ├── Script_Generation_Pipeline/
│   │   ├── Preprocessing/           # OpenStax HTML crawler → Markdown
│   │   ├── Script_With_Dpoints/     # Anthropic + Gemini script generators (with branching)
│   │   ├── Prompt_Rules/            # Script-generation rules fed to the LLM
│   │   ├── _JSON_Templates/         # Output schemas the LLM must follow
│   │   └── _Script_Outputs/         # Example generated scripts
│   ├── Image_Generation_Pipeline/
│   │   ├── Background_Generation/
│   │   ├── Character_Generation/
│   │   ├── Frame_Generation/
│   │   └── Feedback_Retry/          # Regenerate an image from user feedback
│   ├── Video_Generation_Pipeline/
│   │   ├── manim_generator/         # ★ Manim branching-video pipeline — see its README
│   │   ├── video_generator/         # Veo-based live-action pipeline (being replaced, see below)
│   │   └── scenario.json            # Example scenario
│   └── Transcript_Eval_Pipeline/
│       └── transcript_eval/         # Transcript + consistency eval — see its README
│
└── demo_manim_video/                # Pre-rendered Manim demo output (mp4 + srt)
```

---

## Quickstart

### 1. Backend (FastAPI)

```bash
cd BackEnd
python3 -m venv venv && source venv/bin/activate
pip install -r backend_requirement.txt

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
# (equivalently: python main.py)
```

Interactive API docs at <http://localhost:8000/docs>.

API keys are read from `BackEnd/backend.env` (loaded by `main.py` via python-dotenv) or the environment:

```
ANTHROPIC_API_KEY=sk-ant-...   # for model_choice "anthropic"
GEMINI_API_KEY=...             # for model_choice "gemini", image gen, and the Manim planner
```

For Manim video generation, install the extra pipeline requirements into the same venv and point the env at the Kokoro TTS model files (see `BackEnd/Video_Generation_Pipeline/manim_generator/README.md`):

```bash
pip install -r Video_Generation_Pipeline/manim_generator/requirements.txt
```

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

The app is served under the `/openstax/` base path (e.g. <http://localhost:5173/openstax/>). The Vite dev server proxies `/api` to `http://localhost:8000` (see `frontend/vite.config.ts`), so no frontend API configuration is needed. `npm run build` produces a static bundle in `frontend/dist/`.

---

## API endpoints

All routes are mounted under `/api` (see `BackEnd/api.py`).

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/api/initial_script` | Crawls the requested OpenStax section, sends content + user query to the chosen LLM, returns a full script JSON |
| `POST` | `/api/generate_background_image` | Generates the reference background image for a script |
| `POST` | `/api/generate_character_images` | Generates reference character images |
| `POST` | `/api/generate_opening_frames` | Composites opening frames from background + character references |
| `POST` | `/api/retry_generate_background_image` | Regenerate the background (optionally guided by user feedback) |
| `POST` | `/api/retry_generate_character_image` | Regenerate one character image (optionally guided by feedback) |
| `POST` | `/api/retry_generate_opening_frames` | Regenerate opening frames (optionally guided by feedback) |
| `GET` | `/api/image/{image_path}` | Serves a generated PNG back to the UI |
| `GET` | `/api/video/{video_path}` | Serves a generated MP4 back to the UI |
| `POST` | `/api/generate_manim_videos` | Starts Manim branching-video generation for an edited script (async, single worker) |
| `GET` | `/api/manim_video_status/{request_id}` | Polls pipeline progress (`queued` / `assets` / `scene_k_of_n` / `stitching` / `done` / `error`) |

### `POST /api/initial_script` request body

```json
{
  "book_title": "Biology 2e",
  "unit_num": 3,
  "chapter_num": 9,
  "page_num": "9.1",
  "user_query": "A nursing student watches glucose metabolism in real time.",
  "model_choice": "anthropic",
  "video_type": "manim"
}
```

`model_choice`: `"anthropic"` (Claude API), `"gemini"`, or `"local"` (Claude Code CLI). The field is optional: when omitted it resolves to `"anthropic"` if `ANTHROPIC_API_KEY` is set, otherwise to `"local"`. Requesting `"anthropic"` without an API key also falls back to `"local"` (with a warning in the server log).
`video_type`: `"manim"` (animated graphics — the demo centerpiece) or `"scenario"` (live action).

### The `local` model provider (no API key needed)

`model_choice: "local"` shells out to the **Claude Code CLI** (`claude -p`) instead of calling the Anthropic API — it works on any machine with Claude Code installed and logged in (credentials in `~/.claude`), with **no `ANTHROPIC_API_KEY` required**. The backend looks for `claude` on `PATH`, falling back to `~/.local/bin/claude`. Because of the automatic fallback described above, a keyless machine works out of the box: just leave `model_choice` unset (or pick Anthropic in the UI) and script generation runs through the local CLI. Implementation: `BackEnd/Script_Generation_Pipeline/Script_With_Dpoints/local_script_generation.py`.

---

## Script JSON shape

The generated script follows the template in `BackEnd/Script_Generation_Pipeline/_JSON_Templates/script_gen_with_dpoints.json`. Top-level fields:

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Script title |
| `learning_goal` | string | What the viewer should understand |
| `target_audience` | string | Intended learner |
| `total_duration_seconds` | number | Estimated total runtime |
| `visual_style` | string | Overall production direction |
| `setting` | object | Location, lighting, time of day, camera notes, atmosphere |
| `characters` | array | Name, role, appearance, emotional baseline |
| `scenes` | array | Ordered scenes with dialogue, setting, actions, audio, routing |
| `decision_points` | array | Questions with A/B/C choices, correct answer, scene routing |

---

## Manim video generation (demo centerpiece)

`BackEnd/Video_Generation_Pipeline/manim_generator` turns a finalized script into a **branching set of narrated diagram videos**: one Manim clip per scene (Kokoro TTS narration, frozen per-scenario style kit, LLM-generated scene code with automatic render-repair and a grid-layout critic), plus a `manifest.json` describing the decision-point branch graph and a stitched `golden_path.mp4` correct-answers preview. A pre-rendered example lives in `demo_manim_video/`.

**Via the API / UI** — submit the edited script from the frontend, or:

```bash
curl -X POST http://localhost:8000/api/generate_manim_videos \
  -H 'Content-Type: application/json' \
  -d '{"script": { ... }, "request_id": "my-run"}'

curl http://localhost:8000/api/manim_video_status/my-run
```

Output lands in `output/manim_runs/<request_id>/` at the repo root (override with `MANIM_OUTPUT_ROOT`).

**Via the CLI** — from the repo root with the backend venv active:

```bash
PYTHONPATH=BackEnd/Video_Generation_Pipeline python -m manim_generator.cli \
  --script BackEnd/Script_Generation_Pipeline/_Script_Outputs/output_script_with_decision_points_anthropic_new.json \
  --out output/manim_runs --request-id demo --quality m
```

`--quality l` (480p) is fastest for iteration, `h` (1080p) for final renders. A full 8-scene scenario takes roughly 30–60 minutes. Full setup and pipeline details: `BackEnd/Video_Generation_Pipeline/manim_generator/README.md`.

---

## Live-action video generation (Veo → local Wan2.2)

`BackEnd/Video_Generation_Pipeline/video_generator` is the original live-action pipeline: it takes the exported script JSON and produces MP4s scene-by-scene with Google Veo, chaining each clip from the last frame of the previous one.

```bash
cd BackEnd/Video_Generation_Pipeline
export GEMINI_API_KEY=your-key-here

# Generate all scenes
python -m video_generator.cli --scenario scenario.json

# Generate one scene
python -m video_generator.cli --scenario scenario.json --scene-id 3

# Preview the per-clip prompts without generating
python -m video_generator.cli --scenario scenario.json --scene-id 3 --preview-prompt

# Verify each clip against the script as it's generated, regenerating on failure
python -m video_generator.cli --scenario scenario.json --scene-id 3 --verify-clips
```

See `BackEnd/Video_Generation_Pipeline/README.md` for the full flag reference.

> **Note — local generation:** the Veo backend is being replaced by **local Wan2.2 video generation via ComfyUI**, which runs on our own GPU with no cloud API key or per-clip cost. The Manim path above is fully local already (apart from the LLM planner calls) and is what the hosted demo showcases.

---

## Transcript & consistency eval

`BackEnd/Transcript_Eval_Pipeline/transcript_eval` transcribes a generated clip's actual audio, then checks the transcript against the clip's ground-truth `scenario.json` dialogue — catching wrong/garbled dialogue and dialogue attributed to the wrong on-screen character.

```bash
cd BackEnd/Transcript_Eval_Pipeline
export GEMINI_API_KEY=your-key-here

python -m transcript_eval.cli \
  --video path/to/scene3_clip1.mp4 \
  --scenario ../Video_Generation_Pipeline/scenario.json \
  --scene-id 3 --clip-id 1
```

Three stages per clip: local Whisper transcription (free), a fuzzy dialogue match against the script, then a Gemini vision judge that samples frames to confirm the speaking character. Usable standalone or from generation via `video_generator`'s `--verify-clips` flag. See `BackEnd/Transcript_Eval_Pipeline/README.md`.

---

## Deployment

The live demo is served at **<https://lab.darshon.com/openstax/>**:

- The frontend is built with `npm run build` (Vite `base: '/openstax/'`) and served as static files under `/openstax/`.
- The FastAPI backend is reverse-proxied at **`/openstax-api`** on the same host, so the browser reaches the API without CORS or per-environment configuration.

---

## License

Licensed under the [MIT License](LICENSE).
