# Start frames for the i2v runs

The images that went into `LoadImage` (node 17) for every i2v run in
`../generation_log_20260805.json`. The log records them under
`/tmp/Frame_Image_Output/` and `/tmp/Background_Image_Output/`, which no longer
exist; these are the copies ComfyUI kept in its own `input/` directory. Filenames
are unchanged from the log, so a run's `reference_images` entry can be matched
here by basename.

| Run batch | Cast | Script | Start image |
|---|---|---|---|
| 2026-08-05, scenes 1-16 | Jordan, Elena | `../../solo_clip/anthony_scenario.json` | `07e977ab-..._<scene>_opening_frame.png`, one per scene |
| 2026-08-04, scenes 1-8 | Priya, Darnell | not in the repo, see below | `93bc86c5-..._background_reference_image.png`, shared by all 8 |
| 2026-07-30, scene 1 | Maya, Carl | `../../scenario.json` | none, that run was t2v |

The 2026-08-04 batch used an 8-scene script whose source file is not anywhere in
this repo. Its prompts survive only in the log, which is enough to rerun those
clips but not to regenerate them from the scenario.

The per-scene opening frames were produced by
`BackEnd/Image_Generation_Pipeline/Frame_Generation/gemini_frame_generate.py`,
which writes `{request_id}_{scene_id}_opening_frame.png`. The `07e977ab` and
`93bc86c5` prefixes are the request ids of those two generation runs.

Note that `../../reference_images/background_reference_image.png` is a different
image from the `93bc86c5` one here despite the matching name. It is a separate
generation and was not the start frame for anything in the log.

To reuse one, copy it into ComfyUI's `input/` and set node 17's `image` in
`../wan22_i2v_api.json` to its filename, or pass it as
`--i2v-start-image <filename>` to `video_generator.cli`.
