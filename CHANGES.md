# OpenStax Scenario Generator — Changes

## Backend

### New files

**`app/parser.py`**
Scrapes OpenStax HTML chapters to markdown using BeautifulSoup + markdownify.
Includes a `CHAPTER_URLS` dict (one entry for Clinical Nursing Ch.1 already mapped) — add more as needed.

**`app/script_gen.py`**
Calls Claude (`claude-sonnet-4-6`) with the markdown + description and returns a structured JSON script object.

### Updated files

**`requirements.txt`**
Added `anthropic`, `requests`, `beautifulsoup4`, `markdownify`.

**`app/schemas.py`**
- `GenerateRequest` is now structured: `{ textbook, chapters, units, description }`
- `GenerateResponse` now includes the full `script` JSON object
- New `SaveScriptRequest` / `SaveScriptResponse`
- `ScenarioDetail` gets an optional `script` field

**`main.py`**
- `POST /api/scenarios/generate` now runs parser → script gen → persists nodes/edges from real JSON script
- New `PUT /api/scenarios/{id}/script` saves user-modified script and resyncs nodes/edges

---

## API Workflow

### 1. Markdown File Parser (Frontend → Backend)
`POST /api/scenarios/generate`

Request body:
```json
{
  "textbook": "Clinical Nursing",
  "chapters": ["Chapter 1: Patient Assessment"],
  "units": "All Units",
  "description": "A 68-year-old patient presents with chest pain..."
}
```

Backend steps:
1. Scrapes OpenStax HTML for each chapter → markdown
2. Passes markdown + description to Claude
3. Claude returns a JSON script object
4. Persists scenario + nodes/edges to DB

### 2. Original JSON Script (Backend → Frontend)
Response from `POST /api/scenarios/generate`:
```json
{
  "scenario_id": "uuid",
  "script": {
    "title": "...",
    "nodes": [
      {
        "id": "scene_1",
        "scene_number": 1,
        "title": "...",
        "script": "...",
        "video_prompt": "...",
        "is_endpoint": false,
        "choices": [
          {
            "id": "choice_1a",
            "text": "...",
            "destination_scene_id": "scene_2",
            "is_misconception": false,
            "feedback": "..."
          }
        ]
      }
    ]
  }
}
```

Also retrievable via `GET /api/scenarios/{id}` (returns `script` field from stored `script_draft`).

### 3. User Modified JSON Script (Frontend → Backend)
`PUT /api/scenarios/{id}/script`

Request body:
```json
{
  "script": { ... }
}
```

Stores the modified script JSON and resyncs the nodes/edges table.

---

## Frontend

### Design (OpenStax-inspired)
- **Navbar** — sticky white bar with OpenStax orange wordmark + pipe separator
- **Colors** — OpenStax orange `#F47C20` for CTAs, focus rings, step badges; green `#5eb146` for endpoints/success states
- **Background** — `#f5f5f5` page background, white cards with subtle `#e0e0e0` borders

### Setup page (`/`)
- Form fields consolidated into a single white card with section dividers
- Structured API call using `{ textbook, chapters, units, description }`
- Inline hint about 20–30s generation time during loading state

### Editor page (`/scenarios/[id]`)
- Replaced per-node save buttons with a single global **Save Changes** button (top-right)
- Each scene card shows: title, editable script textarea, `video_prompt` subtitle, and rich choice list with A/B/C labels (green = correct path, red = misconception branch)
- Green **Save & Continue to Video Generation** CTA at the bottom

---

## Adding More Chapter URLs

To enable parsing for additional chapters, add entries to `CHAPTER_URLS` in `app/parser.py`:

```python
CHAPTER_URLS = {
    "Clinical Nursing": {
        "Chapter 1: Patient Assessment": "https://openstax.org/...",
        "Chapter 2: Medication Administration": "https://openstax.org/...",
    },
    "Anatomy & Physiology": {
        "Chapter 1: Cell Biology": "https://openstax.org/...",
    },
}
```

If a chapter has no URL configured, the parser falls back to a placeholder string and the LLM generates the script from the description alone.
