# Scenario Studio — Script Generator UI

An internal admin tool for OpenStax. Editors pick a chapter/section from a
textbook, generate an AI-grounded **scenario script** (overview, characters,
branching scenes, decision points), edit it inline, then save it to the
backend for downstream image / video generation.

The UI is wired to the FastAPI backend in `../BackEnd/`:
- `POST /api/initial_script` — generates a script via Anthropic or Gemini,
  grounded in the OpenStax textbook content the crawler scrapes for the
  chosen book / unit / chapter / page.
- `POST /api/modified_script` — receives the user's edited script.

Single-scene regeneration and whole-script revise are wireframed but have no
backend route yet — see [Integration points](#integration-points).

---

## Run it

No build step. It's a single HTML file that loads React + Babel from a CDN.

```bash
# any static server works — pick one:
npx serve .            # serves on :3000 by default
# or
python3 -m http.server 8080
```

Then open the printed URL (e.g. <http://localhost:8080>). The backend must
also be running:

```bash
cd ../BackEnd
ANTHROPIC_API_KEY=... GEMINI_API_KEY=... \
  python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`BackEnd/main.py` allows the common local static-server ports
(3000/5173/8000/8080) by default; for anything else, set
`ALLOWED_ORIGINS=http://my-host:port` on the backend.

To point the UI at a non-default backend, drop a `<script>` ahead of
`api.js` in `index.html`:

```html
<script>window.OS_API_BASE = "http://my-backend:9000";</script>
```

> **Why no build?** Keeping it as plain HTML + in-browser Babel means anyone can
> open the file, edit, and refresh — zero tooling. If the app outgrows this,
> the migration path is Vite + real `.jsx` modules (the components are already
> split along sensible lines).

---

## Files

| File | What it is |
|------|------------|
| `index.html` | The whole app — markup, styles, and the React tree (inline `text/babel`). |
| `api.js` | Backend client (`window.OSApi.fetchInitialScript`, `submitModifiedScript`). |
| `tweaks-panel.jsx` | Reusable "Tweaks" panel (sliders/toggles/radios). Powers the in-app appearance controls. Don't edit unless you're changing the control kit. |
| `docs/data-contracts.md` | The data shape returned by `/api/initial_script` and accepted by `/api/modified_script`. **Read this before changing fields.** |

---

## How the app is laid out

Everything lives in `index.html` inside one `<script type="text/babel">`. Top to
bottom:

1. **`CATALOG`** — the OpenStax textbook library (books → chapters → sections).
   Each chapter carries a `unit` (the backend crawler's `unit_num`) and each
   book a `bookTitle` (the value sent as `book_title`).
2. **`lookupSection` / `buildGenerateRequest`** — turn a UI section ID
   (`"biology2e:09:9.1"`) into the `/api/initial_script` payload.
3. **`SAMPLE_SCRIPT`** — a sample in the backend shape, used by the
   "Load sample script" dev tweak so layout work doesn't require the LLM.
4. **Icons** (`I`) — inline SVGs.
5. **Components** — `Sidebar`, `GeneratePanel`, `SceneCard`, `CharacterCard`,
   `DecisionPointCard`, `GenOverlay`, `VideoModal`, and the root `App`.

### Key interactions
- **Select a section** in the left rail → enables the Generate button.
- **Type a scenario description** + **pick a model** (Anthropic / Gemini)
  in the generate panel.
- **Generate script** → `POST /api/initial_script` → overview, characters,
  scene ribbon, and decision-points render from the response.
- **Pencil on a scene card** → inline edit every backend field
  (type, duration, setting, character actions, camera, dialogue with
  character lookup, audio, routes-to).
- **Pencil on a character card** → edit name, role, appearance subfields,
  emotional baseline.
- **Decision-point cards** → edit the question, choice text, mark the
  correct answer, set each choice's destination scene.
- **Save & continue** → `POST /api/modified_script` with the full edited
  script.
- **Generate scenario video** → still opens the stub render dialog.

---

## Integration points

| Status | What | Where |
|--------|------|-------|
| ✅ wired | Script generation | `App.runGenerate()` → `OSApi.fetchInitialScript` → `POST /api/initial_script` |
| ✅ wired | Save edited script | `App.submitScript()` → `OSApi.submitModifiedScript` → `POST /api/modified_script` |
| 🟡 client-only | Textbook catalog | `CATALOG` in `index.html`. Backed by hand-curated entries that match the OpenStax ABL titles + unit numbers the crawler accepts. Replace with a `/api/catalog` feed if you don't want to maintain it inline. |
| ❌ no endpoint | Single-scene regen | UI affordance removed pending a `POST /api/regenerate_scene` route. |
| ❌ no endpoint | Whole-script revise | UI affordance removed pending a `POST /api/revise_script` route. The old `ReviseModal` component was deleted; reintroduce alongside the endpoint. |
| ❌ no endpoint | Render video | `VideoModal` still alerts. Hand the approved `script` + options to your render backend when one exists. |

---

## Contributing

- Keep `index.html` editable-by-hand: close every tag, double-quote attributes,
  no fancy bundler syntax.
- Match the existing visual system — it follows the OpenStax palette (mostly
  white, navy text `#002569`, orange primary `#f36f21`, supporting green/yellow/
  gray) and the Lato typeface.
- If you add a new field to a scene, update `docs/data-contracts.md` in the same
  PR.
- Big additions (new screens, real backends) should be discussed in an issue
  first.

---

## License

Internal OpenStax project. Add your org's license here before making the repo
public.
