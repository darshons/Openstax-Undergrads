# Elena's Knee (Anthony scenario) — video generation

16-scene interactive nursing scenario, generated via the solo-clip pipeline: one isolated Veo clip per dialogue line (never two characters in the same shot), stitched together per scene. This doc covers running generation end to end.

## Required files

Scenario JSON and reference images:

```
Video_Generation_Pipeline/anthony_scenario_script_with_clips.json
Video_Generation_Pipeline/reference_images_anthony/
  player.png                    (Jordan)
  elena.png                     (Elena)
  instructor.png                (Nurse Reyes)
  background_reference_image.png
```

File names are looked up by `character_id` from the scenario JSON — not cosmetic. If you're pulling these from the original "scene gen 2" source folder instead of an existing checkout, the source files are named `jordan_nursing_student.png`, `elena_patient.png`, `nurse_reyes_supervisor.png`, `background.png` and need renaming to match the list above. The `scene_N_opening_frame.png` storyboard images in that folder aren't consumed by the pipeline.

Character rig and prior scene output:

```
Video_Generation_Pipeline/output/anthony_scenario/
  character_rig.json
  sceneN_raw/
  sceneN_final.mp4
```

None of `output/` is committed to git. `character_rig.json` is the one LLM-generated pose/camera/backdrop/gaze-direction spec per character — regenerating it (rather than reusing an existing one) is non-deterministic and produces different phrasing/backdrop/gaze assignments than whatever's already been generated, so scenes end up visually inconsistent with each other. Get the existing `output/anthony_scenario/` folder (~24MB) from whoever generated the prior scenes and drop it in place before running anything new. Seeding for character continuity is based on the most recently generated clip on disk for that character, not scene order — you don't need every earlier scene to exist, just at least one prior appearance of each character somewhere in `output/anthony_scenario/`.

## Environment

```
cd BackEnd
./venv/bin/python -c "import google.genai, moviepy, whisper"   # sanity check
```

`venv/` isn't committed either. If it doesn't exist:

```
python3 -m venv venv
venv/bin/pip install google-genai moviepy openai-whisper python-dotenv pillow numpy
```

`GOOGLE_API_KEY` needs to be set in `BackEnd/backend.env`.

## Generating a scene

```
./venv/bin/python scratch_generate_anthony_scenario.py --scene-id N
```

One scene at a time. Output: `output/anthony_scenario/sceneN_raw/` (per-line clips) and `sceneN_final.mp4` (stitched). Model defaults to `veo-3.1-fast-generate-preview`; override with `--model`. Cost is roughly $0.80/line at the fast tier (8s clips), $3.20/line at full `veo-3.1`.

Scene 9-16 speaker/line breakdown:

| Scene | Type | Lines | Speakers |
|---|---|---|---|
| 9 | narrative | 3 | elena, player |
| 10 | consequence | 3 | instructor, player |
| 11 | consequence | 3 | instructor, player |
| 12 | resolution | 2 | player |
| 13 | narrative | 2 | elena, instructor |
| 14 | consequence | 2 | instructor, player |
| 15 | consequence | 2 | instructor, player |
| 16 | resolution | 3 | elena, player |

## How generation and stitching work

`solo_clip_pipeline.run_scenario_pipeline_solo_clip` (invoked by the scratch script) flattens each scene's clips into individual dialogue lines, builds one Veo prompt per line via `prompt_builder.build_veo_prompt`, and generates each as an isolated first clip — reference-image-seeded on a character's first appearance in the run, first-frame-seeded (image conditioning from that character's most recent clip) on every appearance after that.

`stitching.stitch` then assembles a scene's raw clips: transcribes each with Whisper, trims to the detected speaking span (dropping any transcribed segment that doesn't share words with the clip's known scripted line — filters out stray unscripted interjections Veo sometimes adds), applies a short audio-only declick fade at the edges, and hard-cuts them together in filename order. No crossfades. Re-running `stitch()` on an existing `sceneN_raw/` directory is free (no Veo calls) — useful after a stitching-only fix.

## Reviewing output

There's no automated pass/fail check wired into this pipeline. Per scene:

- Watch the full clip, not a sample — defects can land anywhere in the duration.
- Verify dialogue against the scenario JSON's exact line text. Whisper transcription plus a manual listen catches invented/dropped words the trim-matching heuristic might not.
- No second character bleeding into a solo shot, even partially or out of focus.
- Gaze: character turned ~45° off-camera per their assigned `gaze_direction` in the rig, not looking at the lens.
- No unrequested camera movement, sound effects, or visual effects (vignette, flare, grain, transitions) — there's a blanket "don't add anything not described" instruction in `prompt_builder.py`, not yet exhaustively validated.

## Retrying a bad clip

Don't delete an existing `sceneN_raw/` outright — move it aside first (`mv sceneN_raw _archive/sceneN_raw_$(date +%Y%m%d_%H%M%S)`) so a prior good version isn't lost. To retry a single clip rather than the whole scene: rebuild that line's prompt via `solo_clip_pipeline._build_line_prompt`, regenerate with `veo_api.generate_first_clip` (reference images if it's that character's first appearance in the run, otherwise a seed frame extracted from their most recent good clip via `solo_clip_pipeline._extract_seed_frame`), overwrite the clip file, then re-run `stitching.stitch` on the directory. If the retried clip was itself the seed source for a later clip, that later clip needs regenerating too.

## Sending output back

`output/` isn't tracked in git. Share `sceneN_raw/` + `sceneN_final.mp4` for finished scenes back out of band (zip, drive, whatever) to merge into the canonical copy.

## Multi-character shots

Every clip in this pipeline shows exactly one character by design — that's what makes speaker attribution reliable. If a scene calls for multiple characters in frame at once with no dialogue (e.g. an establishing shot), that's a separate, one-off generation call outside the normal per-line flow, and needs two extra guarantees beyond the usual prompt: an explicit instruction that all characters' mouths stay fully closed with no jaw/lip movement for the entire clip (a "stay silent" instruction alone is not reliable — Veo has generated full unscripted dialogue between characters despite it), and stripping the clip's audio track in post (`VideoFileClip.without_audio()`) regardless of what the "silent" instruction produces, since a text instruction is not a structural guarantee. Verify by transcribing the result and sampling frames across the entire clip duration, not just a few points — the failure mode showed up mid-clip in testing, not at the start.
