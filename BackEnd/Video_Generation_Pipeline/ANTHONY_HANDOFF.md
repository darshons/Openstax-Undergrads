# Anthony scenario - handoff for next session

Context for a fresh session continuing the Elena's Knee (Anthony) scenario work.
Written 2026-08-06, end of the session that fixed scene 10.

## Goal for the new session

1. Get all 16 scenes generated.
   Scenes 9, 11, 12, 14, 15, 16 are still missing.
   Check whether the coworker already generated any of these before regenerating them from scratch - see the "coworker's branch" warning below for how to actually get their files.
2. Build an extremely barebones HTML page that plays all 16 scene videos in numeric order (1 through 16), for Anthony to review.
   Plain sequential playback only - no branching/decision-point logic, no framework, no build step.
   The real interactive branching experience is the separate StudentPlayer React app already in the repo; this is just a review reel.

## Branch

Work happens on `solo-clip-single-character-frames`, not `main`.
Do not use `solo-clip-integration` (see warning below).

## Current scene status

Generated (10 of 16), in `Video_Generation_Pipeline/output/anthony_scenario/sceneN_final.mp4`:
1, 2, 3, 4, 5, 6, 7, 8, 10, 13

Missing (6 of 16):
9, 11, 12, 14, 15, 16

`output/` is not git-tracked, so this status only reflects what's on this machine right now.

## Uncommitted fixes from this session - handle before generating anything else

Two pipeline bugs were found and fixed while regenerating scene 10.
As of this handoff they are uncommitted on disk (`git status --short` shows `M solo_clip_pipeline.py` and `?? transcribe.py`).
Confirm with the user whether these got committed/pushed by the end of the prior session - if not, commit them first, since every one of the 6 remaining scenes will hit the same crash otherwise.

- **`video_generator/solo_clip_pipeline.py:230`**: unpacked `generate_first_clip()`'s return as 2 values, but that function returns 3 (`video_obj, attempts, recovered_error`) since the trim-accuracy commit added the third field.
  This crashed on the first clip of every scene run through the production script, not just scene 10 - it's very likely the exact bug behind the coworker's earlier "scene 10 not working" report.
  Fix: unpack 3 values.
- **`Transcript_Eval_Pipeline/transcript_eval/transcribe.py`**: `stitching.py` imports `transcribe_clip` from this module, but the module had been deleted by commit `73a736a` ("Replace the outdated evaluator with a llm as a judge") before `stitching.py`'s dependency on it was ever written.
  Fix: restored the original Whisper-based implementation via `git show 73a736a^:BackEnd/Transcript_Eval_Pipeline/transcript_eval/transcribe.py`.

## Coworker's branch (`origin/solo-clip-integration`) - do not merge or pull from it

Investigated this earlier in the prior session: it diverged from `main` at commit `c32647b` (2026-07-23), which is before any of the Anthony scenario work existed.
It is missing `anthony_scenario_script_with_clips.json`, `reference_images_anthony/`, and every fix made on `solo-clip-single-character-frames` (prompt hardening, the reference-image name-label leak fix, the trim-accuracy fix, etc).
It's a separate, parallel restructuring of the pipeline (new `solo_clip/` package layout), not a cleanup of this branch's work.

If the coworker already generated any of the missing scenes, get the raw files directly from them (`sceneN_raw/` + `sceneN_final.mp4`, out of band - zip/drive/whatever, per the existing README's "Sending output back" section) rather than merging or pulling their branch.

## How to generate a missing scene

Full mechanics, required files, and the review checklist are in `Video_Generation_Pipeline/ANTHONY_SCENARIO_README.md`.
Quick version:

```
cd BackEnd
venv/bin/python scratch_generate_anthony_scenario.py --scene-id N
```

Roughly $0.80/line at the fast Veo tier.
Scene 9-16 line counts and speakers are already tabulated in that README.

## HTML player

Single static HTML file, no build step.
Plays `sceneN_final.mp4` for N = 1 through 16 in order (e.g. a `<video>` element that advances to the next scene on its `ended` event, plus a manual "Next" button as a fallback).
Point it at `Video_Generation_Pipeline/output/anthony_scenario/` (or a copy of the 16 final files) so it can be opened directly as a local file or served with a trivial static server.
