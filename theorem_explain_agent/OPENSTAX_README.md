# OpenStax → TheoremExplainAgent

This fork adds a pipeline for turning **OpenStax textbook sections** into narrated
Manim explanation videos, using the existing TheoremExplainAgent (TEA) generator.

The generator already accepts a JSON list of `{theorem, description}` items via
`--theorems_path`. The only new piece is **`openstax_adapter.py`**, which converts
OpenStax CNXML books into exactly that format. One OpenStax *section* → one video.

## What was set up on this machine

- Python **3.12** virtualenv at `.venv/` (the repo requires 3.12).
- All deps from `requirements.macos.txt` (a macOS-friendly copy of `requirements.txt`:
  `kokoro-onnx[gpu]` → `kokoro-onnx`, plus `pyobjc`).
- System tools via Homebrew: `espeak-ng`, `portaudio`, `sox` (ffmpeg + MacTeX were
  already present).
- Kokoro TTS model files in `models/` (`kokoro-v0_19.onnx`, `voices.bin`).
- `.env` configured with `GEMINI_API_KEY` and Kokoro paths.
- Current Gemini models added to `src/utils/allowed_models.json`
  (`gemini-3.5-flash`, `gemini-3-pro-preview`, `gemini-2.5-pro`, `gemini-2.5-flash`).

Every command below assumes:

```bash
cd theorem_explain_agent_repo
source .venv/bin/activate          # IMPORTANT: activate, don't just call .venv/bin/python
export PYTHONPATH=$(pwd):$PYTHONPATH
```

> **Why `activate` matters:** the renderer shells out to a bare `manim` command, which
> resolves via `PATH`. If you only call `.venv/bin/python generate_video.py` without
> putting the venv's `bin` on `PATH`, the subprocess may pick up a *different* system
> `manim` that lacks `manim_voiceover`, and every voiceover scene fails with
> `ModuleNotFoundError: No module named 'manim_voiceover'`. Activating the venv (or
> running `export PATH="$(pwd)/.venv/bin:$PATH"`) fixes this.

## Step 1 — get an OpenStax book

OpenStax publishes book source as CNXML in the `openstax/osbooks-*` GitHub repos.
A shallow clone is enough:

```bash
git clone --depth 1 https://github.com/openstax/osbooks-college-physics-bundle.git
```

Each bundle contains:
- `collections/<book>.collection.xml` — the table of contents (chapters → sections).
- `modules/m#####/index.cnxml` — one file per section.

Other books: `osbooks-college-algebra-bundle`, `osbooks-chemistry-bundle`,
`osbooks-biology-bundle`, `osbooks-calculus-bundle`, etc. (search the
[openstax GitHub org](https://github.com/openstax)).

## Step 2 — convert to topic JSON

```bash
# Whole book:
python openstax_adapter.py \
    --book-dir osbooks-college-physics-bundle \
    --collection college-physics-2e \
    --out data/openstax/college_physics.json

# One chapter only, capped at 5 sections, skipping "Introduction" stubs:
python openstax_adapter.py \
    --book-dir osbooks-college-physics-bundle \
    --collection college-physics-2e \
    --chapter "Kinematics" \
    --max-sections 5 \
    --skip-intro \
    --out data/openstax/kinematics.json
```

The adapter maps:
- `theorem`  ← section title (`<document><title>`)
- `description` ← learning objectives + opening body paragraphs (markup stripped,
  capped at `--max-desc-chars`, default 1200)

It also keeps `chapter`, `module_id`, and `source` for traceability (the generator
ignores extra keys).

Flags: `--chapter` (case-insensitive substring on chapter title), `--max-sections`,
`--max-desc-chars`, `--skip-intro`, `--collection` (slug, filename, or path; optional
if the book has one collection).

## Step 3 — generate videos

```bash
python generate_video.py \
    --model        "gemini/gemini-3.5-flash" \
    --helper_model "gemini/gemini-3.5-flash" \
    --theorems_path data/openstax/kinematics.json \
    --output_dir   "output/openstax_kinematics" \
    --max_scene_concurrency 3 \
    --max_topic_concurrency 1 \
    --verbose
```

For higher-quality animations (fewer render failures) use `gemini/gemini-3-pro-preview`
or `gemini/gemini-2.5-pro` as `--model`. Output (per topic) lands in
`output/<exp>/<topic_slug>/`; the final stitched video is the
`*_combined.mp4` there.

### Useful generator flags
- `--sample_size N` — only process the first N topics from the JSON.
- `--only_plan` — generate scene outlines/plans without rendering (cheap dry run).
- `--check_status` — report plan/code/render status for every topic.
- `--use_rag --manim_docs_path ... --chroma_db_path ...` — retrieval over Manim docs
  for better code (download the docs bundle linked in the main README).
- `--use_visual_fix_code` — let a VLM inspect rendered frames and repair the code.

## Tips for OpenStax specifically

- **Pick visual sections.** Topics with geometry/graphs/processes (kinematics,
  forces, significant figures, stoichiometry) animate far better than prose-heavy
  history/intro sections. `--skip-intro` drops the worst offenders.
- **Math notation.** MathML in CNXML is flattened to plain text in the description.
  That's fine as context, but for heavy-equation sections, `gemini-3-pro-preview`
  handles the LaTeX in generated Manim much more reliably than flash.
- **Cost/time.** Each section is several LLM calls plus Manim renders — budget a few
  minutes and a handful of cents to a few cents per video on flash. Start with
  `--sample_size 1` or `--max-sections 1` to validate before a batch run.
- **Attribution.** OpenStax content is CC-BY (some CC-BY-NC-SA, e.g. College Physics).
  Keep the attribution from the book's license when you publish derived videos.

## Bugs fixed in the upstream repo (already applied here)

- **`src/core/video_renderer.py` combine step** — it picked the *highest code version*
  folder for each scene, but the version that actually rendered an mp4 isn't always the
  newest (a retry can regenerate code that then fails to render). It now searches newest→
  oldest for a folder that actually contains an mp4, so combine no longer aborts with
  `Missing video for scene N`. If a run renders all scenes but doesn't produce a combined
  video, just re-run with `--only_combine`.

- **Parallel render deadlock** — with `--max_scene_concurrency > 1`, a scene that throws
  during render could deadlock the async gather. Use `--max_scene_concurrency 1` (serial)
  for reliable runs; it's slower but doesn't hang.

## Files added by this integration
- `openstax_adapter.py` — the CNXML → topic-JSON converter.
- `requirements.macos.txt` — macOS-installable dependency set.
- `data/openstax/` — generated topic JSON (demo + intro chapter).
- `OPENSTAX_README.md` — this file.
```
