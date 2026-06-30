# OpenStax Chemistry — Limiting Reactant Prototype

A 60–90 second Manim Community Edition prototype demonstrating an interactive
educational scenario built from OpenStax chemistry content.

## Render

```bash
pip install manim
manim -pql limiting_reactant.py LimitingReactantScene
```

- `-p` previews on completion, `-ql` renders at 480p for fast iteration.
- For the spec'd 720p30, the file already pins `pixel_width=1280`,
  `pixel_height=720`, `frame_rate=30` via `config`, so any quality flag
  produces 720p30. To get the full-quality cached render, drop `-ql`:
  `manim -p limiting_reactant.py LimitingReactantScene`.

## What the prototype demonstrates

1. **Recurring character with consistent visual identity** — `ProfessorChen`
   is a `VGroup` subclass with `wave()`, `point_at(obj)`, and `say(text)`
   methods. Same instance can appear across hundreds of scenarios.
2. **Subject-specific visual asset** — `Beaker` is a parametric VGroup
   (`label`, `mass`, `fill_level`, `fill_color`) reusable across any
   chemistry scenario.
3. **Textbook-grounded explanation, animated diagrammatically** — MathTex
   stoichiometry walk-through using 6 g H₂ + 32 g O₂, identifying O₂ as
   the limiting reactant via mole comparison.
4. **Pause-and-answer moment** — final scene holds a multiple-choice
   question frame for ~6 s, ready for a player layer to gate playback
   on a user response.

## Scene timing

| Scene | Duration | Content |
| --- | --- | --- |
| 1. Intro | ~10 s | Chen fades in, waves, poses the problem |
| 2. Setup | ~20 s | Beakers + balanced equation, Chen points |
| 3. Concept | ~30 s | Gram→mole conversions, ratio check, O₂ highlighted as limiting |
| 4. Decision | ~15 s | "Which reactant is limiting?" with A/B/C options |

## Why this beats text-to-video for OpenStax content

- **Deterministic character consistency** — Chen is the same VGroup every
  render. Veo/Sora can't guarantee her goggles stay on between scenes.
- **Near-zero per-render cost** — local Manim render vs. per-second
  generation pricing.
- **Scientific accuracy** — correct glassware shape, correctly balanced
  equation, correct stoichiometric arithmetic, correct visual conventions
  (limiting reactant highlighted, not just narrated).
- **Composable with OpenStax assets** — the same `Beaker` and `MathTex`
  primitives that drive this scene can ingest problem JSON straight from
  the OpenStax textbook to autogenerate scenarios.

## What a production system would extend

- **Illustrator-designed character.** Replace `ProfessorChen`'s primitive
  body with `SVGMobject("assets/chen.svg")`. The class's public surface
  (`wave`, `point_at`, `say`) stays unchanged — scenario scripts don't
  need to know.
- **Asset library.** Same pattern for `GraduatedCylinder`, `BunsenBurner`,
  `Erlenmeyer`, `RoundBottomFlask`, `Buret`, then beyond chemistry:
  `Neuron`, `FreeBodyDiagram`, `SupplyDemandCurve`, `Histogram`.
- **Voiceover.** Manim's `manim-voiceover` plugin lets you script Chen's
  speech and auto-sync TTS with animation, removing the static caption
  bubbles.
- **Scenario generator.** A small layer that consumes OpenStax problem
  JSON (`{reactants: [{formula:"H2", mass:6}, ...], question:"..."}`)
  and emits a `Scene` like this one. The hand-written prototype is the
  proof that the target output is achievable; the generator becomes the
  product.
- **Branching from the decision frame.** The pause-frame becomes a real
  interactive checkpoint when wrapped in a player that listens for the
  learner's selection and routes to one of three follow-up Manim scenes
  (correct, partial, incorrect — each with tailored remediation).
- **Reusable answer-key & analytics hooks.** The multiple-choice options
  are already labelled A/B/C in code; a thin export step would emit them
  to a learning-record store alongside the video.

---

## Getting Started for Developers

### 1. Start the local Postgres database

```bash
docker run --name prototype-db \
  -e POSTGRES_PASSWORD=YourPasswordHere \
  -e POSTGRES_DB=scenario_db \
  -p 5432:5432 \
  -d postgres
```

### 2. Configure environment variables

```bash
cp backend/.env.example backend/.env
# Open backend/.env and replace YourPasswordHere with the password you used above.
```

### 3. Create and activate a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 5. Build the database tables

```bash
cd backend
python init_db.py
```

### 6. Seed test data

```bash
python seed_db.py
```

You should see output like:
```
Seed complete.
Created scenario ID: <uuid>
```

### 7. Start the API server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The interactive API docs will be available at `http://localhost:8000/docs`.
