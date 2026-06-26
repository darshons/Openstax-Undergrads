# AI Video Generator Research & Improvement Notes

Research into popular open-source AI video generators, the patterns worth borrowing, and
concrete improvements for our Veo-based nursing-scenario pipeline. The bar throughout:
**high-leverage but easy to adopt — no overengineering.**

---

## 1. What we have today

Our pipeline generates interactive educational nursing videos with Google **Veo 3.1**. Single
source of truth is `scenario.json` (characters, scenes, clips, dialogue, decision points).

| File | Responsibility |
|------|----------------|
| `video_gen.py` | `build_veo_prompt()` assembles a structured text prompt; `generate_video()` submits/polls/downloads; `burn_captions()` overlays captions with MoviePy; logging to `output/generation_log.json`. |
| `stitch_videos.py` | Long-form via Veo's *extension* feature. `build_clip_prompts()` splits a scene into per-clip prompts; `run_scene_pipeline()` chains clips with a settle delay + mid-chain checkpointing. |
| `run_batch.py` | Experimentation runner (model compare, sprite vs no-sprite, prompt variations). |

**Things we already do well** (worth keeping — several studied repos converge on these):

- **Structured prompt assembly** from JSON rather than free text.
- **Numbered speaker-lock** in the dialogue block to stop Veo swapping voices between characters.
- **Dynamic character-consistency block** built from each character's appearance (skin/hair/uniform).
- **`is_continuation` anchor** on extension clips so the model doesn't reset appearance/lighting/layout.
- **Negative prompts** to suppress unwanted captions/subtitles in-frame.
- **Extension settle-time + checkpointing** so a mid-chain failure doesn't lose the spent hops.
- **Generation logging** for reproducibility/review.

---

## 2. What the studied repos do

### Wan2.2 (Wan-Video) — open diffusion model
- T2V / I2V / TI2V / S2V (audio-driven) / character animation, built on a Mixture-of-Experts DiT.
- **Prompt extension via an LLM (Qwen)** as a preprocessing step to enrich prompt detail.
- **Segmented long-form generation with overlapping conditioning frames** for temporal coherence.
- Most of the value (MoE routing, high-compression VAE, consumer-GPU inference) is *model-internal*.

### HunyuanVideo-1.5 (Tencent) — open diffusion model
- Lightweight 8.3B DiT + 3D causal VAE; T2V and I2V; super-resolution to 1080p.
- **Automatic prompt rewriting via an LLM (Qwen) before diffusion**, with *separate* rewrite
  behavior for T2V vs I2V. Their docs are explicit: *"longer, detailed prompts significantly
  improve output quality."*
- Progressive resolution then dedicated super-res; caching/distillation for speed. Again, model-internal.

### OpenMontage (calesthio) — agentic orchestration framework
- Turns a coding agent into a video studio: research, script, scene plan, assets, edit, compose.
- **Explicit scene-planning stage gated by JSON schema validation** (15 schemas) — catches malformed
  plans before any spend.
- **Word-level caption timing via WhisperX** — frame-accurate, TikTok-style reveals.
- Multi-track audio mixing (narration/music/SFX with ducking), per-platform output profiles, and an
  auditable checkpoint/decision log with cost governance (estimate, reserve, approve, cap).

### waoowaoo (waooAI) — full AI film-production web app
- Novel-text to finished video: script analysis, consistent character/environment assets,
  storyboard, multi-character voice synthesis. Next.js + queue (BullMQ) + MySQL/Prisma.
- Mostly *product/infrastructure* shaped — the reusable idea is the explicit
  **script -> assets -> storyboard -> audio** staging and consistent-asset generation.

### Cross-cutting takeaway

Two patterns recur independently across these projects and map cleanly onto what we already have:

1. **LLM prompt rewriting/expansion before generation** — done by **3 of 4** (Wan2.2,
   HunyuanVideo, OpenMontage). It's the single most universal, highest-ROI trick, and it's nearly
   free for us because we already hold a Gemini client.
2. **Accurate (word-level) caption timing** — OpenMontage treats this as standard; it's a direct
   fix for a known weakness in our `burn_captions()`.

---

## 3. Recommended improvements (prioritized)

### Priority 1 — LLM prompt enhancement (the universal pattern)

**Problem.** `build_veo_prompt()` (`video_gen.py:47`) emits a terse, template-shaped prompt. Every
diffusion repo studied expands prompts with an LLM first because richer cinematic/visual detail
measurably improves output.

**Recommendation.** Add an *optional* enhancement pass: send the assembled structured prompt to a
Gemini **text** model via the existing `genai.Client`, asking it to enrich visual/cinematic detail
**while preserving the hard constraints** — exact dialogue lines, numbered speaker order, character
appearance, and "no text overlays." Keep the deterministic structured prompt as the base and treat
the LLM output as an enrichment layer. Gate it behind a `--enhance-prompt` flag so default behavior
is unchanged.

Sketch (illustrative — not yet applied):

```python
# new helper in video_gen.py, called after build_veo_prompt()
ENHANCE_INSTRUCTIONS = (
    "Rewrite the following video prompt to be more vivid and cinematic "
    "(lighting, framing, texture, motion). HARD RULES: do not change any "
    "dialogue text or its speaker order; do not add or remove characters; "
    "keep every character's appearance exactly; keep 'no text overlays'. "
    "Return only the rewritten prompt."
)

def enhance_prompt(client, base_prompt, model="gemini-2.5-flash"):
    resp = client.models.generate_content(
        model=model, contents=f"{ENHANCE_INSTRUCTIONS}\n\n---\n{base_prompt}"
    )
    return resp.text.strip()
```

**Why it's easy:** no new dependency (reuses `google-genai`), ~30 lines, opt-in.

**Caveat to enforce:** the enhancer must not alter dialogue text or invent characters — exactly the
failure modes our speaker-lock and consistency blocks already guard against. Constrain it hard in
the instructions and, ideally, keep the structured dialogue/consistency blocks appended verbatim
*after* the enhanced description rather than letting the LLM rewrite them.

### Priority 2 — Accurate caption timing

**Problem.** `burn_captions()` distributes dialogue **evenly** across the clip
(`clip_duration = dialogue_duration / max(len(dialogue), 1)` — `video_gen.py:229`). Spoken lines
aren't equal length, so captions drift out of sync with speech.

**Option (a) — proportional timing, zero new deps (recommended default).** Allocate each line a
share of the duration proportional to its character/word count, with a small minimum floor, instead
of equal slices:

```python
weights = [max(len(l["line"]), 1) for l in dialogue if l.get("character_id")]
total = sum(weights)
# each line i gets dialogue_duration * weights[i] / total
```

A few lines of change to the timing loop; meaningfully better sync at no cost.

**Option (b) — transcription-based, accurate (optional upgrade).** Veo renders real spoken audio,
so transcribe the output with word-level timestamps (`faster-whisper` / WhisperX, as OpenMontage
does) and place captions on actual speech boundaries. Highest fidelity, but adds a dependency and
runtime — present as an opt-in, not the default.

---

## 4. Lower-priority / optional ideas

Listed for completeness — explicitly *out of the requested scope*, but small if ever wanted:

- **Scenario schema validation.** Extend `load_scenario()` (`video_gen.py:150`) to verify every
  `dialogue.character_id` resolves to a defined character and clips are well-formed, failing *before*
  spending Veo budget. One small validation function.
- **Cost/time preflight.** Before `run_batch.py` / `stitch_videos.py` fire dozens of paid jobs,
  print estimated clip count, total seconds, and job count (a scaled-down version of OpenMontage's
  budget governance).

---

## 5. Explicitly out of scope (avoid overengineering)

We use a **hosted API (Veo)**, so most of the studied projects' headline tricks are handled by the
API and not ours to reimplement:

- Local diffusion-model hosting, MoE/VAE internals, super-resolution, caching/distillation
  (Wan2.2, HunyuanVideo) — API-side concerns.
- Multi-provider scoring matrices, agentic multi-layer skill systems (OpenMontage).
- Full web-app + task-queue + DB architecture (waoowaoo).

Adopting any of these would add large surface area for little benefit at our current scale. The two
prioritized changes above capture the durable, model-agnostic wins.

---

## Sources

- OpenMontage — https://github.com/calesthio/OpenMontage
- Wan2.2 — https://github.com/Wan-Video/Wan2.2
- waoowaoo — https://github.com/waooAI/waoowaoo
- HunyuanVideo-1.5 — https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5
