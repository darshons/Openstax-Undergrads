# Wan reference workflows and run archive

The inputs behind the Wan videos generated in July and August 2026. Kept here so
the old clips can be reproduced or inspected without needing the machine they were
made on.

## The ComfyUI workflows

`wan22_t2v_api.json` and `wan22_i2v_api.json` are the hand-built ComfyUI API
workflows that were validated by hand before any of this was automated. They are
the reference `local_api.build_workflow()` mirrors, and the docstring at the top of
`local_api.py` points at `wan22_i2v_api.json` by name.

Load either one into ComfyUI with the API-format import, or POST it to `/prompt`
directly, to generate a single clip without going through the pipeline at all.
That is the fastest way to check whether a problem is in the model setup or in the
Python around it.

| | T2V | I2V |
|---|---|---|
| Nodes | 16 | 17, the extra one is `LoadImage` |
| Latent source | `EmptyHunyuanLatentVideo` | `WanImageToVideo` |
| Models | `Wan2.2-T2V-A14B-{High,Low}Noise-Q6_K.gguf` | `Wan2.2-I2V-A14B-{High,Low}Noise-Q6_K.gguf` |
| LoRAs | `wan2.2_t2v_lightx2v_4steps_lora_v1.1_{high,low}_noise` | `wan2.2_i2v_lightx2v_4steps_lora_v1_{high,low}_noise` |
| Seed as saved | 42 | 30003 |

Both are 832x480, 81 frames, 8 steps, cfg 1.0, 16 fps, shared text encoder
`umt5_xxl_fp8_e4m3fn_scaled.safetensors` and VAE `wan_2.1_vae.safetensors`.

The one thing the pipeline adds that is not in these files is the optional
character LoRA, inserted as node 18 on the low-noise branch when
`--character-lora` is passed. Everything else it builds matches these graphs node
for node.

## The run archive

`generation_log_20260805.json` is the pipeline's own log for every Wan run:
46 scene runs, 30 of which succeeded, 84 clips total. Each entry carries the mode,
the reference image, wall time, output filename, file size, and the full prompt for
every clip.

`prompts_index.md` is the same content rendered as readable markdown, grouped by
scene run with each clip's prompt in a code block. Use this one to find a prompt;
use the JSON if you want to compute something over the runs.

Failed runs are kept in both. All 16 failures were a single bug, a call passing a
`default_setting` argument that `build_clip_prompts` did not accept, which is fixed.
None of them were the model producing unusable video, so their prompts are still
worth reading.

The videos these produced are under `../output/` and are not committed, since the
repo ignores `output/`. They are on the machine that rendered them.

## Reproducing a clip

The prompts in the archive are the finished strings that went to `CLIPTextEncode`,
so nothing needs to be rebuilt to reuse one. Paste it into node 9 of the matching
workflow, set the seed to 30003, and generate.

To go through the pipeline instead, the scenario that produced most of these runs
is `../scenario.json`:

```bash
cd BackEnd/Video_Generation_Pipeline
python -m video_generator.cli --scenario scenario.json --scene-id 1 --dry-run
```

`--dry-run` prints the exact payload it would submit, which can be diffed against
these reference files if a run starts behaving differently from the archive.
