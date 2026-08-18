# OpenStax Scenario Studio

An authoring tool that turns OpenStax textbook sections into branching
educational video scenarios. An editor picks a section, describes a situation,
and gets back a structured script with scenes, characters, and decision points.
They edit it in the browser, then render it to video. Students watch the result
and make choices that route them down different branches.

Built during the OpenStax summer 2026 undergraduate internship by Team DJ YAM.
This README covers the whole system and is written for whoever picks it up next.

## The short version

There are three video renderers and they solve different problems. All three
consume the same script JSON, so a scenario can be rendered any of the three
ways without editing the script.

**Manim diagrams** draw explanatory graphics: flowcharts, labeled figures,
graphs. An LLM writes Manim code, the pipeline renders it, repairs it when it
fails, and critiques the layout of what came out. Narration is local TTS
(Kokoro). Fully local except for the LLM calls. See
[`manim_generator/README.md`](BackEnd/Video_Generation_Pipeline/manim_generator/README.md).

**Wan 2.2 character video** renders people: a nurse talking to a patient, a
student in a lab. It runs on one machine's GPU through ComfyUI, so rendering
costs nothing. **As of this writing it exists but isn't reachable from the
API** — see [Known gaps](#known-gaps). See
[`Video_Generation_Pipeline/README.md`](BackEnd/Video_Generation_Pipeline/README.md).

**Solo clip (Veo)** is a live-action character-video technique that renders
each dialogue line as its own isolated Veo clip with one character alone in
frame, then stitches them. It structurally eliminates the wrong-speaker-in-
frame artifact that chaining every character into one continuously-extended
shot is prone to. It runs on Google Veo rather than locally, so it costs real
money, and **it is currently the only live-action renderer the API actually
calls** — see [Known gaps](#known-gaps). See
[`solo_clip/README.md`](BackEnd/Video_Generation_Pipeline/solo_clip/README.md).

## Layout

```
frontend/                          React 19, Vite, Tailwind, TypeScript
  src/App.tsx                      Router: / (home), /studio, /player, /player/:scenarioId
  src/Studio.tsx                   The creator app: script/assets/video review pages
  src/pages/                       HomePage, JoinPage, PlayerPage (student flow)
  src/components/                  canvas, assets, video, student, layout
  src/data/catalog.ts              21 books, 468 sections, generated from the live OpenStax ToC
  src/lib/api.ts                   every backend call in one file

BackEnd/
  main.py                          FastAPI entry, CORS, router mounting
  API/
    instructor_api.py              authoring routes, /instructor_api
    instructor_api_helpers.py      background jobs, shared helpers
    student_api.py                 playback routes, /student_api
  Script_Generation_Pipeline/
    Preprocessing/html_crawler.py  OpenStax HTML to Markdown
    Script_With_Dpoints/           anthropic, gemini, and local script generators
    Prompt_Rules/                  the rules fed to the LLM
    _JSON_Templates/                output schemas the LLM must follow
    _Script_Outputs/                example generated scripts
  Image_Generation_Pipeline/       backgrounds, characters, opening frames, retry-with-feedback
  Video_Generation_Pipeline/
    manim_generator/               Manim diagram pipeline
    video_generator/               Wan 2.2 local pipeline, plus the deprecated Veo extension-chain path
    solo_clip/                     one-isolated-clip-per-speaker Veo technique (currently the wired-in renderer)
  Transcript_Eval_Pipeline/        transcript and consistency evaluation

examples/                          standalone hand-written Manim scenes
demo_manim_video/                  pre-rendered demo output
```

## Running it

### Backend

Requires Python 3.12 - `backend_requirement.txt` pins `pillow==10.4.0`, which
has no prebuilt wheel for 3.13+ and fails to build from source without local
jpeg headers.

The server imports the Manim pipeline at module load time, so both
requirements files are needed just to start it, not only for Manim
generation:

```bash
cd BackEnd
python3.12 -m venv venv && source venv/bin/activate
pip install -r backend_requirement.txt
pip install -r Video_Generation_Pipeline/manim_generator/requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

API docs at http://localhost:8000/docs.

Copy `BackEnd/.env.example` to `BackEnd/backend.env` (loaded by `main.py` via
python-dotenv). Every key is optional — the backend boots and generates
scripts with zero configuration by falling back to the `local` provider
(Claude Code CLI, no API key needed):

```
ANTHROPIC_API_KEY=sk-ant-...   # script generation, provider "anthropic"
GEMINI_API_KEY=...             # provider "gemini", all image generation, Manim planning, Veo/solo-clip generation
SUPABASE_URL=...               # publishing a scenario + the student fetch flow
SUPABASE_KEY=...
KOKORO_MODEL_PATH=/abs/path/to/kokoro-v0_19.onnx   # optional — Manim narration degrades to silent audio if unset
KOKORO_VOICES_PATH=/abs/path/to/voices.bin
```

Script generation has a third provider, `local`, which shells out to the
Claude Code CLI and needs no key at all. If `model_choice` is empty, the
backend picks `anthropic` when `ANTHROPIC_API_KEY` is set and falls back to
`local` otherwise, so the app runs with no keys configured at all if you only
want script generation.

For actual Manim narration (not silent placeholder audio), point the env at
the Kokoro TTS model files - see
`BackEnd/Video_Generation_Pipeline/manim_generator/README.md`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Served under `/openstax/`, so http://localhost:5173/openstax/. In dev the
frontend talks to `http://localhost:8000` directly (CORS is open
server-side) — no proxy needed. Override with `VITE_API_BASE`. `npm run
build` produces a static bundle in `frontend/dist/`.

### Rendering video without the UI

Neither pipeline needs the server running. This is the fastest way to
evaluate output quality.

```bash
# Manim diagrams
PYTHONPATH=BackEnd/Video_Generation_Pipeline python -m manim_generator.cli \
  --script BackEnd/Script_Generation_Pipeline/_Script_Outputs/output_script_with_decision_points_anthropic_new.json \
  --out output/manim_runs --request-id demo --quality l

# Wan character video, validate first
cd BackEnd/Video_Generation_Pipeline
python -m video_generator.cli --scenario scenario.json --scene-id 1 --model local --dry-run
python -m video_generator.cli --scenario scenario.json --scene-id 1 --model local
```

`--dry-run` (local model only) builds and validates every ComfyUI payload
without submitting anything — run it first on any new machine, since it needs
a running ComfyUI server with the right GGUF custom nodes and model files
present. `--quality l` (480p) is fastest for Manim iteration, `h` (1080p) for
final renders.

## API

Routes are mounted at `/instructor_api` and `/student_api`. Full schemas at
`/docs`.

| Method | Route | What it does |
|---|---|---|
| POST | `/instructor_api/initial_script` | Crawl a section, generate a branching script |
| POST | `/instructor_api/generate_background_image` | Scene background |
| POST | `/instructor_api/generate_character_images` | Character portraits |
| POST | `/instructor_api/generate_opening_frames` | Composite opening frames from background + character references |
| POST | `/instructor_api/retry_generate_background_image` | Regenerate a background from written feedback |
| POST | `/instructor_api/retry_generate_character_image` | Regenerate a character from written feedback |
| POST | `/instructor_api/retry_generate_opening_frames` | Regenerate one scene's opening frame from written feedback |
| POST | `/instructor_api/generate_videos` | Start live-action video generation (always solo-clip/Veo — see Known gaps) |
| GET | `/instructor_api/video_status/{request_id}` | Poll it |
| POST | `/instructor_api/generate_manim_videos` | Start Manim generation |
| GET | `/instructor_api/manim_video_status/{request_id}` | Poll it |
| GET | `/instructor_api/manim_assets/{request_id}` | Inventory of everything a Manim run produced (plans, code versions, error logs, critic snapshots) |
| GET | `/instructor_api/manim_asset/{request_id}/{path}` | Serve one Manim intermediate by its run-relative path |
| POST | `/instructor_api/regenerate_manim_scene/{request_id}/{scene_id}` | Re-render one Manim scene from an edited plan, code, or script |
| GET | `/instructor_api/video/{path}` | Serve an mp4 |
| GET | `/instructor_api/image/{path}` | Serve an image |
| POST | `/instructor_api/upload_project_info` | Publish a finished scenario (requires `SUPABASE_URL`/`SUPABASE_KEY`) |
| GET | `/student_api/assets/{project_id}` | Everything the student player needs for a published scenario |

Both generation endpoints (`generate_videos`, `generate_manim_videos`) return
immediately and write progress to a status file on disk; the corresponding
status endpoints are plain file reads. Nothing is held in process memory, so
restarting the API does not lose a run in flight.

## Script JSON shape

The generated script follows the template in
`BackEnd/Script_Generation_Pipeline/_JSON_Templates/script_gen_with_dpoints.json`.
Top-level fields:

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

## Notes for integrating this

The parts most worth knowing if you are folding this into an existing system.

**The script JSON is the contract.** Everything downstream reads the same
shape: top-level `scenes[]`, `characters[]`, and `decision_points[]`. All
three renderers consume it, the player consumes it, and the eval pipeline
consumes it. If you replace one component, match that schema and the rest
keeps working.

**Scenes render independently.** No renderer resolves routing during
generation. Decision points drive the player, not the renderer. That means
scenes can be regenerated in any order, in parallel across machines, or one
at a time after an edit, without invalidating the branch graph.

**Cost sits in the LLM/Veo calls, not the Manim or Wan rendering.** Manim and
Wan rendering are free (local compute). What costs money is script
generation, image generation, Manim planning/codegen/repair, Veo clip
planning, and every solo-clip Veo call itself. Both LLM paths already have
keyless alternatives: `local` script generation via the Claude Code CLI, and
`llm_client.py` on the Manim side.

**Manim renders must stay serial.** Parallel Manim subprocesses deadlock. The
API runs the pipeline in a one-worker executor for this reason. Scaling means
separate processes with separate media directories, or separate machines.

**The Veo extension-chain path (`video_generator`) is deprecated but
intact.** It's kept so old runs stay reproducible and because its per-clip
evaluation harness is still useful. Development moved to `solo_clip` because
of the wrong-speaker artifact described above.

## Branches

`main` is the canonical branch — everything in this README describes it. The
demo-specific branch (`anthony-demo`: a hardcoded example scenario, ~30MB of
pre-baked demo video/image binaries, and a "type anthony to join" shortcut in
the join screen) has had its real, reusable fixes (StudentPlayer UX,
GeneratePanel cleanup, a couple of real bugs) merged into `main`; the
demo-only hardcoding and binaries were deliberately left out and still live
only on `anthony-demo` if ever needed again. Two other branches had open pull
requests (`fix/manim-temp-output-root` / #14, `theorem-explain-openstax` /
#4); both are closed — #14's real content (Manim temp-dir output default,
intermediate-asset endpoints) is already merged into `main`, and #4 (a
third, unintegrated video pipeline vendored from an external repo) was
closed as out of scope.

## Known gaps

Listed plainly so nobody rediscovers them the hard way.

- **The Wan (local) vs Veo backend choice in the Studio UI does nothing.**
  `POST /instructor_api/generate_videos` always runs solo-clip Veo
  generation regardless of which renderer the user picked — the request
  body's `backend` field isn't declared on the Pydantic model, so FastAPI
  silently drops it. A user who picks "Wan" expecting free local rendering
  will actually trigger paid Veo generation without realizing it. Fixing
  this means wiring `request.backend` through to a real dispatch between
  `solo_clip` and `video_generator`'s local Wan2.2/ComfyUI path — not
  attempted yet since it needs a real GPU + ComfyUI server to test against.
- **The Wan pipeline outputs video only.** No voice track, no narration, no
  lip sync. Dialogue in the scenario JSON drives what characters appear to
  be doing, not speech. Only the Manim pipeline has narration, via Kokoro
  TTS.
- **Character consistency past about 4 chained clips drifts** in the
  extension-chain (`video_generator`) path, because each clip seeds from
  the previous clip's last frame and errors compound. `solo_clip` avoids
  this structurally by never chaining.
- **The Manim layout critic looks at one still frame per round**, so it
  catches overlap but not problems that only appear in motion.
- **There is no queue in front of ComfyUI.** Two concurrent runs against the
  same server will interleave their jobs.

## License

MIT. See [LICENSE](LICENSE).
