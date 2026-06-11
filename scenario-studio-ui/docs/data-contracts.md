# Data contracts

The UI is driven by two data structures defined at the top of `index.html`. This
is the interface your backend needs to satisfy. Keep this doc in sync whenever
you change a shape.

---

## 1. Catalog — `CATALOG`

The textbook library shown in the left rail.

```js
const CATALOG = [
  {
    id: "biology2e",            // unique slug, used in section IDs
    title: "Biology 2e",        // display name
    sub: "Clark · Douglas · Choi", // author line
    color: "#9ccb3b",           // spine accent (any CSS color)
    chapters: [
      {
        n: "09",                // chapter number (string — keeps leading zeros)
        name: "Cellular Respiration",
        secs: [
          { n: "9.1", t: "Energy in Living Systems" },
          { n: "9.2", t: "Glycolysis" },
          // ...
        ]
      }
    ]
  }
];
```

### Section selection IDs
A selected section is tracked as a single string key:

```
`${book.id}:${chapter.n}:${section.n}`   // e.g. "biology2e:09:9.2"
```

The set of selected IDs is what you send to the LLM as "context to ground the
script in".

---

## 2. Script — scene objects

`MOCK_SCRIPT` is an **array of scene objects**, rendered left-to-right as
storyboard cards. This is what your script-generation LLM must return.

```js
{
  n: 3,                         // 1-based scene number (also the render order)
  tag: "DEMO",                  // one of TAGS (see below) — drives the colored label
  duration: "1:05–2:10",        // human-readable time range, shown on the card
  title: "Glycolysis — splitting glucose in the cytoplasm",
  narration: "In the cytoplasm, a six-carbon glucose molecule…",  // the voiceover script
  visual: "2D molecular diagram: glucose marches through 10 steps…", // direction for the animator/renderer
  onscreen: "Net yield: 2 ATP · 2 NADH · 2 pyruvate",  // on-screen text overlay; "\n" allowed for line breaks
  cites: ["Bio 2e §9.2"]        // array of source citations (free-form strings)
}
```

### Scene tags — `TAGS`
```js
const TAGS = ["HOOK", "CONCEPT", "DEMO", "PROBLEM", "RECAP"];
```
Each tag has a matching CSS class (`.scene-tag.hook`, `.scene-tag.concept`, …)
that sets its color. If you add a tag, add a style rule for it too.

### Field notes
- **`narration`** — the only field used for the word count in the card footer.
- **`onscreen`** — split on `"\n"` when rendered, so multi-line overlays work.
- **`cites`** — shown as chips; hidden entirely when the "Show citations" tweak
  is off. Keep the strings short.
- **`duration`** — purely display. The UI doesn't parse it, so any format is
  safe, but `m:ss–m:ss` matches the existing style.

---

## 3. What the revise actions expect

These handlers in `App` currently mutate the mock data. When you wire real
endpoints, preserve these signatures so the UI doesn't change:

| Handler | Input | Expected output |
|---------|-------|-----------------|
| `runGenerate()` | selected section IDs + nothing else | a full `script` array (scene objects) |
| `regenerateScene(idx, note)` | scene index + user's free-text feedback | a single replacement scene object for that index |
| `reviseAll(note)` | user's free-text direction | a full `script` array, same length/structure, rewritten |

> **Player note:** the companion video-player module (not in this repo) extends
> the scene object with `isQuestion: true` and a `question: { prompt, context,
> options[], correct, explain }` block for interactive checkpoints. If your
> generator should produce those, add the fields here when you implement them.
