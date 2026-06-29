# OpenStax Scenario Studio

An internal authoring tool that lets OpenStax content editors generate, review, and refine **interactive educational scenario scripts** grounded in real OpenStax textbook content — then hand them off to a video generation pipeline.

Built by Team DJ YAM.

---

## What it does

1. **Pick a textbook section** from the sidebar (Biology 2e, Clinical Nursing, Anatomy & Physiology, and more).
2. **Describe a scenario** — e.g. *"A nursing student watches a patient's glucose metabolism in real time."*
3. **Choose a model** (Anthropic Claude or Google Gemini) and a **video type** (Veo · Scenario or Manim · Graphics).
4. **Generate** — the backend crawls the relevant OpenStax HTML, feeds it to the LLM, and returns a structured JSON script with scenes, characters, decision points, and a setting description.
5. **Edit inline** — scene cards, character cards, and a setting panel are all editable in the browser. Decision-point branches are shown as an interactive tree; click a choice pill to mark it as the correct answer.
6. **Save & export** — submit the finished script back to the backend, or download it as JSON.

---

## Project structure

```
.
├── scenario-studio-ui/     # Frontend — single HTML file, no build step
│   ├── index.html          # The whole app (React + inline Babel)
│   ├── api.js              # Backend client (fetchInitialScript, submitModifiedScript)
│   ├── tweaks-panel.jsx    # Reusable appearance-controls panel
│   └── docs/
│       └── data-contracts.md   # API request/response shapes
│
└── BackEnd/                # FastAPI backend
    ├── main.py             # App entry point + CORS config
    ├── api.py              # Route handlers (/api/initial_script, /api/modified_script)
    ├── Script_Generation_Pipeline/
    │   ├── Preprocessing/  # OpenStax HTML crawler → Markdown
    │   ├── script_with_dpoints/   # Anthropic + Gemini LLM script generators
    │   └── JSON_Templates/ # Output schema the LLM must follow
    └── Image_Generation_Pipeline/
        ├── Character_Generation/
        └── Frame_Generation/
```

---

## Running locally

### 1. Start the backend

```bash
cd BackEnd
python3 -m venv venv && source venv/bin/activate
pip install -r backend_requirement.txt

# Set your API keys
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=...

python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API docs at <http://localhost:8000/docs>.

### 2. Serve the UI

No build step needed — it's plain HTML.

```bash
cd scenario-studio-ui
npx serve .          # serves on :3000
# or
python3 -m http.server 8080
```

Open the printed URL. The UI auto-connects to `http://localhost:8000`; to override, add before `api.js` in `index.html`:

```html
<script>window.OS_API_BASE = "http://my-backend:9000";</script>
```

---

## API endpoints

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/api/initial_script` | Crawls the requested OpenStax section, sends content + user query to the chosen LLM, returns a full script JSON |
| `POST` | `/api/modified_script` | Receives the user-edited script for downstream processing |

### `POST /api/initial_script` request body

```json
{
  "book_title": "Biology 2e",
  "unit_num": 3,
  "chapter_num": 9,
  "page_num": "9.1",
  "user_query": "A nursing student watches glucose metabolism in real time.",
  "model_choice": "anthropic",
  "video_type": "scenario"
}
```

`model_choice`: `"anthropic"` (Claude) or `"gemini"`.  
`video_type`: `"scenario"` (Veo-style live action) or `"manim"` (animated graphics).

---

## Script JSON shape

The generated script follows the template in `BackEnd/Script_Generation_Pipeline/JSON_Templates/script_gen_with_dpoints.json`. Top-level fields:

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

See `scenario-studio-ui/docs/data-contracts.md` for the full schema.

---

## UI features at a glance

- **Decision tree view** — trunk scenes flow horizontally; branching scenes drop below each decision point. Click a wrong-answer pill to mark it correct without scrolling to the DP card.
- **Inline editing** — every field on every scene, character, and setting card is editable. Large text stays readable in edit mode.
- **Undo duplicate** — the ↩ Undo duplicate button in the toolbar restores the previous state after any scene duplication.
- **Choice reordering** — ↑ / ↓ buttons in decision-point cards let you reorder choices so the correct answer isn't locked to position A.
- **Zoom** — 50 %–150 % canvas zoom in the toolbar.
- **Export** — downloads the current script as `scenario_script.json`.

---

## License

Internal OpenStax project — add your org's license before making this repo public.
