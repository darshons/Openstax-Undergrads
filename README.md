# OpenStax Scenario Studio

An authoring tool that turns OpenStax textbook sections into branching
educational video scenarios. An editor picks a section, describes a situation,
and gets back a structured script with scenes, characters, and decision points.
They edit it in the browser, then render it to video. Students watch the result
and make choices that route them down different branches.

Built during the OpenStax summer 2026 undergraduate internship by Team DJ YAM.
This README covers the whole system and is written for whoever picks it up next.

<!-- VIDEO: drop a demo recording here.
     On GitHub, edit this file in the browser and drag an mp4 into the editor.
     GitHub uploads it and leaves a https://github.com/user-attachments/... link
     that plays inline. Good candidates: a full scenario walkthrough, one Wan
     character scene, one Manim diagram scene. -->

## The short version

There are two independent video pipelines and they solve different problems.

**Manim diagrams** draw explanatory graphics: flowcharts, labeled figures,
graphs. An LLM writes Manim code, the pipeline renders it, repairs it when it
fails, and critiques the layout of what came out. Narration is local TTS. See
[`manim_generator/README.md`](BackEnd/Video_Generation_Pipeline/manim_generator/README.md).

**Wan 2.2 character video** renders people: a nurse talking to a patient, a
student in a lab. It runs on one machine's GPU through ComfyUI, so rendering
costs nothing. See
[`Video_Generation_Pipeline/README.md`](BackEnd/Video_Generation_Pipeline/README.md).

Both read the same script JSON, so a scenario can be rendered either way without
editing the script. That was the main design constraint and it held.

There is also **solo clip**, a third technique that renders each dialogue line as
its own isolated Veo clip with one character alone in frame, then stitches them.
It structurally eliminates the wrong-speaker-in-frame artifact that extension
chaining is prone to. It runs on Veo rather than locally, so it costs money, and
it is isolated from the main pipeline. See
[`solo_clip/README.md`](BackEnd/Video_Generation_Pipeline/solo_clip/README.md).

## Where the project got to

Working end to end. An editor can go from a textbook section to a watchable
branching scenario without leaving the browser.

Real numbers from the runs behind the demo:

| | |
|---|---|
| OpenStax books in the catalog | 21 |
| Sections addressable | 468 |
| Wan scene runs logged | 46, of which 30 succeeded |
| Wan clips generated | 84 |
| Finished character video produced | 424 seconds |
| GPU cost for all of it | $0.00 |
| Time per 5 seconds of character video | 5 to 6 minutes on one RTX 3090 |
| Time for an 8 scene Manim scenario | 30 to 60 minutes |
| Offline tests | 28, passing |

The 16 Wan runs that failed were all one bug, a call passing an argument that
`build_clip_prompts` did not accept. It is fixed. None of the failures were the
model producing unusable video.

The honest limitation is speed. Neither pipeline is interactive. A full scenario
is a coffee break at best and a lunch break at worst, which is why both run as
background jobs that write progress to a status file and why the UI polls rather
than blocks.

## Layout

```
frontend/                          React 19, Vite, Tailwind, TypeScript
  src/pages/                       HomePage, JoinPage, PlayerPage
  src/components/                  canvas, assets, video, student, layout
  src/data/catalog.ts              21 books, 468 sections, generated from the live OpenStax ToC
  src/lib/api.ts                   every backend call in one file

BackEnd/
  main.py                          FastAPI entry, CORS, router mounting
  API/
    instructor_api.py              authoring routes, /instructor_api
    instructor_api_helpers.py      background jobs, backend dispatch
    student_api.py                 playback routes, /student_api
  Script_Generation_Pipeline/
    Preprocessing/html_crawler.py  OpenStax HTML to Markdown
    Script_With_Dpoints/           anthropic, gemini, and local script generators
    Prompt_Rules/                  the rules fed to the LLM
    _JSON_Templates/               output schemas the LLM must follow
    _Script_Outputs/               example generated scripts
  Image_Generation_Pipeline/       backgrounds, characters, opening frames, retry-with-feedback
  Video_Generation_Pipeline/
    manim_generator/               Manim diagram pipeline
    video_generator/               Wan 2.2 local pipeline, plus the deprecated Veo path
    solo_clip/                     one-isolated-clip-per-speaker Veo technique
  Transcript_Eval_Pipeline/        transcript and consistency evaluation

examples/limiting_reactant.py      standalone hand written Manim scene
demo_manim_video/                  pre-rendered demo output
```

## Running it

### Backend

```bash
cd BackEnd
python3 -m venv venv && source venv/bin/activate
pip install -r backend_requirement.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

API docs at http://localhost:8000/docs.

Keys are read from `BackEnd/backend.env` or the environment:

```
ANTHROPIC_API_KEY=sk-ant-...   # script generation, provider "anthropic"
GEMINI_API_KEY=...             # provider "gemini", image generation, Manim planning, clip planning
KOKORO_MODEL_PATH=/abs/path/to/kokoro-v0_19.onnx
KOKORO_VOICES_PATH=/abs/path/to/voices.bin
```

Script generation has a third provider, `local`, which shells out to the Claude
Code CLI and needs no key at all. If `model_choice` is empty, the backend picks
`anthropic` when `ANTHROPIC_API_KEY` is set and falls back to `local` otherwise,
so the app runs with no keys configured at all if you only want script generation.

For video, install the extra pipeline requirements into the same venv:

```bash
pip install -r Video_Generation_Pipeline/manim_generator/requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Served under `/openstax/`, so http://localhost:5173/openstax/. The dev server
proxies `/api` to port 8000. Override the backend with `VITE_API_BASE`.
`npm run build` produces a static bundle in `frontend/dist/`.

### Rendering video without the UI

Both pipelines have CLIs and neither needs the server running. This is the fastest
way to evaluate output quality.

```bash
# Manim diagrams
PYTHONPATH=BackEnd/Video_Generation_Pipeline python -m manim_generator.cli \
  --script BackEnd/Script_Generation_Pipeline/_Script_Outputs/output_script_with_decision_points_anthropic_new.json \
  --out output/manim_runs --request-id demo --quality l

# Wan character video, validate first
cd BackEnd/Video_Generation_Pipeline
python -m video_generator.cli --scenario scenario.json --scene-id 1 --dry-run
python -m video_generator.cli --scenario scenario.json --scene-id 1
```

`--dry-run` builds and validates every ComfyUI payload without submitting
anything. Run it first on any new machine; it catches the three things that
actually go wrong, which are a wrong ComfyUI path, a missing model file, and a
ComfyUI install without the GGUF custom nodes.

## API

Routes are mounted at `/instructor_api` and `/student_api`. Full schemas at
`/docs`.

| Method | Route | What it does |
|---|---|---|
| POST | `/instructor_api/initial_script` | Crawl a section, generate a branching script |
| POST | `/instructor_api/generate_background_image` | Scene background |
| POST | `/instructor_api/generate_character_images` | Character portraits |
| POST | `/instructor_api/retry_generate_background_image` | Regenerate a background from written feedback |
| POST | `/instructor_api/retry_generate_character_image` | Regenerate a character from written feedback |
| POST | `/instructor_api/generate_videos` | Start character video generation |
| GET | `/instructor_api/video_status/{request_id}` | Poll it |
| POST | `/instructor_api/generate_manim_videos` | Start Manim generation |
| GET | `/instructor_api/manim_video_status/{request_id}` | Poll it |
| GET | `/instructor_api/video/{path}` | Serve an mp4 |
| GET | `/instructor_api/image/{path}` | Serve an image |
| POST | `/instructor_api/upload_project_info` | Publish a finished scenario |
| GET | `/student_api/assets/{project_id}` | Everything a player needs for a scenario |

One caveat as of the latest commit on main. `Part 1/? of updating/correcting API
files` removed `generate_opening_frames` and `retry_generate_opening_frames` from
the backend, but `frontend/src/lib/api.ts` still calls both. Until the rest of
that refactor lands, the opening-frame step in the UI will 404. The opening frame
is what seeds image-to-video generation, so this is worth resolving before the
next full run.

Both generation endpoints return immediately and write progress to a status file
on disk. Both status endpoints are plain file reads. Nothing is held in process
memory, so restarting the API does not lose a run in flight.

## Notes for integrating this

The parts most worth knowing if you are folding this into an existing system.

**The script JSON is the contract.** Everything downstream reads the same shape:
top level `scenes[]`, `characters[]`, and `decision_points[]`. Both video
pipelines consume it, the player consumes it, and the eval pipeline consumes it.
If you replace one component, match that schema and the rest keeps working. The
authoritative version is in
`BackEnd/Script_Generation_Pipeline/_JSON_Templates/script_gen_with_dpoints.json`.

**Scenes render independently.** Neither pipeline resolves routing during
generation. Decision points drive the player, not the renderer. That means scenes
can be regenerated in any order, in parallel across machines, or one at a time
after an edit, without invalidating the branch graph.

**Rendering is pluggable at one function.** `run_video_generation()` in
`instructor_api_helpers.py` dispatches on a `backend` string, currently `local` or
`veo`. Adding a third renderer means adding a branch there and a module with the
same `run_scenario_pipeline_*` shape, which takes a scenario and an
`on_scene_complete` callback. Nothing above that function needs to change.

**Cost sits in the LLM calls, not the rendering.** Local rendering is free. What
costs money is script generation, image generation, Manim planning and codegen and
repair, and Wan clip planning. If cost matters, that is where to look. Both LLM
paths already have keyless alternatives: `local` script generation via the Claude
Code CLI, and `llm_client.py` on the Manim side.

**Clip planning still calls Gemini on the local video path.** The rendering is
free, the planning is not, so `GEMINI_API_KEY` is required for the API path
regardless of which video backend is selected. The Wan CLI skips planning and uses
the clips already in the scenario JSON, so the CLI is genuinely keyless.

**Manim renders must stay serial.** Parallel Manim subprocesses deadlock. The API
runs the pipeline in a one worker executor for this reason. Scaling means separate
processes with separate media directories, or separate machines.

**The Veo path is deprecated but intact.** It is kept so old runs stay
reproducible and because its per-clip evaluation harness is genuinely useful. The
project moved off it on cost.

**Solo clip is deliberately not wired in.** It imports prompt building and Veo
call machinery from `video_generator` rather than duplicating it, but nothing
depends on it, and it can be deleted without touching anything else. If the
wrong-speaker artifact matters more than cost for a given scenario, that is the
technique to reach for. Porting its one-character-per-shot idea onto the local Wan
backend is the obvious next piece of work and would get the artifact fix at zero
render cost.

## Branches and tags

`main` is the handoff state. `anthony-demo` holds the final demo build, 10 commits
ahead of main, not yet merged. Two branches have open pull requests, `#14`
(`fix/manim-temp-output-root`) and `#4` (`theorem-explain-openstax`).

Everything else was cleaned up. Twenty five stale branches were deleted, and every
unmerged one was tagged `archive/<branch-name>` first, so nothing was lost. To
recover one:

```bash
git checkout -b recovered archive/video-experimenting
```

`git tag -l 'archive/*'` lists them.

## Known gaps

Listed plainly so nobody rediscovers them the hard way.

- The Wan pipeline outputs video only. No voice track, no narration, no lip sync.
  Dialogue in the scenario JSON drives what characters appear to be doing, not
  speech. Only the Manim pipeline has narration, via Kokoro TTS.
- Character consistency past about 4 chained clips drifts, because each clip seeds
  from the previous clip's last frame and errors compound. Short scenes work
  around it.
- The Manim layout critic looks at one still frame per round, so it catches
  overlap but not problems that only appear in motion.
- There is no queue in front of ComfyUI. Two concurrent runs against the same
  server will interleave their jobs.
- `geometry_author.py` and its two prompt files in `manim_generator/` are
  uncommitted work in progress on iterative still-frame geometry authoring. They
  are not wired into the pipeline.

## License

MIT. See [LICENSE](LICENSE).
