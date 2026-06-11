# Scenario Studio — Script Generator UI

An internal admin tool for OpenStax. Editors select chapters &amp; sections from a
textbook, generate an AI-grounded **scenario script** as a storyboard of scene
cards, then revise scenes (with AI or by hand) before sending the script off to
be rendered as a video.

This repo contains **only the front-end UI** for the script-generation step. The
LLM call, the textbook ingest, and the video-render pipeline are stubbed — see
[Integration points](#integration-points).

---

## Run it

No build step. It's a single HTML file that loads React + Babel from a CDN.

```bash
# any static server works — pick one:
npx serve .
# or
python3 -m http.server 8000
```

Then open <http://localhost:8000>. You can also just double-click `index.html`,
but a local server is recommended so the `tweaks-panel.jsx` import resolves
cleanly in all browsers.

> **Why no build?** Keeping it as plain HTML + in-browser Babel means anyone can
> open the file, edit, and refresh — zero tooling. If the app outgrows this,
> the migration path is Vite + real `.jsx` modules (the components are already
> split along sensible lines).

---

## Files

| File | What it is |
|------|------------|
| `index.html` | The whole app — markup, styles, and the React tree (inline `text/babel`). |
| `tweaks-panel.jsx` | Reusable "Tweaks" panel (sliders/toggles/radios). Powers the in-app appearance controls. Don't edit unless you're changing the control kit. |
| `docs/data-contracts.md` | The data shapes the UI consumes. **Read this before wiring a backend.** |

---

## How the app is laid out

Everything lives in `index.html` inside one `<script type="text/babel">`. Top to
bottom:

1. **`CATALOG`** — the mocked textbook library (books → chapters → sections).
2. **`MOCK_SCRIPT`** — a sample generated script (array of scene objects).
3. **Icons** (`I`) — inline SVGs.
4. **Components** — `Sidebar`, `GeneratePanel`, `SceneCard`, `GenOverlay`,
   `ReviseModal`, `VideoModal`, and the root `App`.

The two data constants at the top are the contract. Swap them for real data and
the UI just works — see `docs/data-contracts.md`.

### Key interactions
- **Select sections** in the left rail → they become context pills.
- **Generate script** → runs a mocked 4-step generation, then renders the
  storyboard.
- **Click a scene** → revise popover (AI regenerate with feedback, or "Edit
  manually").
- **Pencil icon** on a card → inline manual edit of every field.
- **Revise script** (action bar) → apply one direction to all scenes.
- **Generate scenario video** → opens the render dialog (currently stubbed).

---

## Integration points

Search the code for these to find where to plug in real services:

| Looking for | Where | Replace with |
|-------------|-------|--------------|
| Textbook catalog | `const CATALOG = [...]` | Your real books/chapters/sections feed. |
| Script generation | `runGenerate()` in `App` | A call to your LLM. It should return an array matching the scene schema. |
| Single-scene regen | `regenerateScene(idx, note)` | LLM call that regenerates one scene from the user's note. |
| Whole-script revise | `reviseAll(note)` | LLM call that rewrites every scene under one direction. |
| Render video | the `VideoModal` primary button | Hand the approved script + options to your render backend. |

All four currently use `setTimeout` to fake latency and return canned data.

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
