"""Local ComfyUI Wan2.2 backend — drop-in replacement for the Veo path.

Submits Wan2.2 T2V (default) or I2V jobs to a locally running ComfyUI server
(http://127.0.0.1:8188) using the same per-clip prompts that prompt_builder
generates for Veo. No Google/Gemini API key is required anywhere on this path.

The node graph mirrors the proven wan22_i2v_api.json workflow:

    1,2   UnetLoaderGGUF       (Wan2.2 A14B high-noise / low-noise GGUF)
    3,4   LoraLoaderModelOnly  (lightx2v 4-step distill LoRAs, high / low)
    5,6   ModelSamplingSD3     (shift=5.0)
    7     CLIPLoader           (umt5_xxl text encoder)
    8     VAELoader            (wan_2.1_vae)
    9,10  CLIPTextEncode       (positive / negative)
    11    WanImageToVideo (i2v, + node 17 LoadImage)  or  EmptyHunyuanLatentVideo (t2v)
    12,13 KSamplerAdvanced     (2-stage: high-noise steps 0-4, low-noise steps 4-8)
    14    VAEDecode
    15    CreateVideo (fps=16)
    16    SaveVideo   (h264 mp4)
    18    LoraLoaderModelOnly  (optional character LoRA on the low-noise branch only)

Rendered mp4s land under /home/darshon/comfyui/output/.
"""

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from .logging_utils import OUTPUT_DIR

# ── ComfyUI server / filesystem layout ──────────────────────────────────────
COMFY_API = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
COMFY_ROOT = Path(os.environ.get("COMFY_ROOT", "/home/darshon/comfyui"))
COMFY_INPUT_DIR = COMFY_ROOT / "input"
COMFY_OUTPUT_DIR = COMFY_ROOT / "output"
COMFY_MODELS_DIR = COMFY_ROOT / "models"

# ── model files (must exist under COMFY_MODELS_DIR) ─────────────────────────
LOCAL_MODELS = {
    "t2v": {
        "unet_high": "Wan2.2-T2V-A14B-HighNoise-Q6_K.gguf",
        "unet_low": "Wan2.2-T2V-A14B-LowNoise-Q6_K.gguf",
        "lora_high": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
        "lora_low": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
    },
    "i2v": {
        "unet_high": "Wan2.2-I2V-A14B-HighNoise-Q6_K.gguf",
        "unet_low": "Wan2.2-I2V-A14B-LowNoise-Q6_K.gguf",
        "lora_high": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
        "lora_low": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
    },
}
CLIP_MODEL = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE_MODEL = "wan_2.1_vae.safetensors"

# Where ComfyUI actually resolves each loader's filename (first match wins).
_MODEL_SEARCH_DIRS = {
    "unet_name": ("diffusion_models", "unet"),
    "lora_name": ("loras",),
    "clip_name": ("text_encoders", "clip"),
    "vae_name": ("vae",),
}

# ── generation defaults (mirroring wan22_i2v_api.json) ──────────────────────
DEFAULT_WIDTH = 832
DEFAULT_HEIGHT = 480
DEFAULT_LENGTH = 81  # frames @ 16 fps ≈ 5 s
DEFAULT_FPS = 16
DEFAULT_SEED = 30003
DEFAULT_STEPS = 8
BOUNDARY_STEP = 4  # high-noise model handles steps [0,4), low-noise [4,8)
DEFAULT_SHIFT = 5.0
DEFAULT_CFG = 1.0  # lightx2v distill LoRAs want cfg 1.0

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, text, subtitles, captions, watermark, "
    "static image, jpeg artifacts, oversaturated, photorealistic, 3D render, "
    "realistic skin texture, extra people, crowd"
)

POLL_INTERVAL_SECONDS = 15
GENERATION_TIMEOUT_SECONDS = 3600

MODEL_KEY_LOCAL = "wan2.2-local"


class LocalGenerationError(RuntimeError):
    """A ComfyUI job failed, timed out, or produced no video."""


class WorkflowValidationError(ValueError):
    """The built workflow references missing nodes or missing model files."""


# ─────────────────────────────────────────────────────────────────────────────
# Workflow construction
# ─────────────────────────────────────────────────────────────────────────────

def build_workflow(
    prompt: str,
    mode: str = "t2v",
    start_image: str = None,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    length: int = DEFAULT_LENGTH,
    seed: int = DEFAULT_SEED,
    filename_prefix: str = "wan22/scenario_clip",
    character_lora: str = None,
    character_lora_strength: float = 1.0,
) -> dict:
    """Build the ComfyUI API node graph for one clip.

    mode: "t2v" (text-to-video, default) or "i2v" (image-to-video —
          requires start_image, a filename inside ComfyUI's input/ dir).
    character_lora: optional LoRA filename (models/loras) applied to the
          low-noise branch only, mirroring the maya_lora pilot driver.
    """
    if mode not in LOCAL_MODELS:
        raise ValueError(f"mode must be one of {sorted(LOCAL_MODELS)}, got {mode!r}")
    if mode == "i2v" and not start_image:
        raise ValueError("i2v mode requires start_image (a file in ComfyUI's input/).")

    m = LOCAL_MODELS[mode]
    wf = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": m["unet_high"]}},
        "2": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": m["unet_low"]}},
        "3": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["1", 0], "lora_name": m["lora_high"], "strength_model": 1.0},
        },
        "4": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["2", 0], "lora_name": m["lora_low"], "strength_model": 1.0},
        },
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": DEFAULT_SHIFT}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": DEFAULT_SHIFT}},
        "7": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": CLIP_MODEL, "type": "wan", "device": "default"},
        },
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_MODEL}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": prompt}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": negative_prompt}},
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["5", 0],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": DEFAULT_STEPS,
                "cfg": DEFAULT_CFG,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": BOUNDARY_STEP,
                "return_with_leftover_noise": "enable",
            },
        },
        "13": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["6", 0],
                "add_noise": "disable",
                "noise_seed": seed,
                "steps": DEFAULT_STEPS,
                "cfg": DEFAULT_CFG,
                "sampler_name": "euler",
                "scheduler": "simple",
                "latent_image": ["12", 0],
                "start_at_step": BOUNDARY_STEP,
                "end_at_step": DEFAULT_STEPS,
                "return_with_leftover_noise": "disable",
            },
        },
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["8", 0]}},
        "15": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": DEFAULT_FPS}},
        "16": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["15", 0],
                "filename_prefix": filename_prefix,
                "format": "mp4",
                "codec": "h264",
            },
        },
    }

    if mode == "i2v":
        # Mirror wan22_i2v_api.json: LoadImage → WanImageToVideo wraps the
        # text conditioning and emits the start latent.
        wf["17"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["11"] = {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["9", 0],
                "negative": ["10", 0],
                "vae": ["8", 0],
                "start_image": ["17", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
            },
        }
        cond_pos, cond_neg, latent = ["11", 0], ["11", 1], ["11", 2]
    else:
        # T2V: plain empty video latent; conditioning goes straight from the
        # text encoders into both samplers.
        wf["11"] = {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {"width": width, "height": height, "length": length, "batch_size": 1},
        }
        cond_pos, cond_neg, latent = ["9", 0], ["10", 0], ["11", 0]

    wf["12"]["inputs"].update({"positive": cond_pos, "negative": cond_neg, "latent_image": latent})
    wf["13"]["inputs"].update({"positive": cond_pos, "negative": cond_neg})

    if character_lora:
        # Character LoRA on the LOW-noise branch only (identity lives in low
        # noise) — node 4 (lightx2v low) → 18 (character) → node 6.
        wf["18"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["4", 0],
                "lora_name": character_lora,
                "strength_model": character_lora_strength,
            },
        }
        wf["6"]["inputs"]["model"] = ["18", 0]

    return wf


def build_payload(workflow: dict) -> dict:
    """The exact JSON body POSTed to ComfyUI's /prompt endpoint."""
    return {"prompt": workflow}


# ─────────────────────────────────────────────────────────────────────────────
# Workflow validation (used by --dry-run and the unit tests)
# ─────────────────────────────────────────────────────────────────────────────

def _model_file_exists(input_key: str, filename: str) -> bool:
    return any(
        (COMFY_MODELS_DIR / sub / filename).exists()
        for sub in _MODEL_SEARCH_DIRS[input_key]
    )


def validate_workflow(workflow: dict, check_input_image: bool = False) -> list:
    """Return a list of problems (empty = valid).

    Checks: every node-reference input points at an existing node id, and
    every model filename resolves to a real file under COMFY_MODELS_DIR.
    With check_input_image=True, LoadImage filenames must exist in input/.
    """
    problems = []
    node_ids = set(workflow)
    for nid, node in workflow.items():
        if "class_type" not in node or "inputs" not in node:
            problems.append(f"node {nid}: missing class_type/inputs")
            continue
        for key, val in node["inputs"].items():
            # node reference: ["<node_id>", <output_index>]
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                if val[0] not in node_ids:
                    problems.append(
                        f"node {nid} input '{key}' references missing node {val[0]}"
                    )
            elif key in _MODEL_SEARCH_DIRS:
                if not _model_file_exists(key, val):
                    dirs = ", ".join(
                        f"models/{d}" for d in _MODEL_SEARCH_DIRS[key]
                    )
                    problems.append(
                        f"node {nid}: {key}='{val}' not found in {dirs}"
                    )
            elif key == "image" and check_input_image:
                if not (COMFY_INPUT_DIR / val).exists():
                    problems.append(
                        f"node {nid}: input image '{val}' not found in {COMFY_INPUT_DIR}"
                    )
    return problems


def check_server_node_types(workflow: dict) -> list:
    """Cross-check every class_type against the live server's /object_info
    (read-only GET). Returns problems; empty list if all known or server
    unreachable (in which case a note is returned instead of failing hard)."""
    try:
        with urllib.request.urlopen(f"{COMFY_API}/object_info", timeout=10) as r:
            object_info = json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        return [f"note: could not reach ComfyUI at {COMFY_API} ({e}) — skipped class_type check"]
    return [
        f"node {nid}: class_type '{node['class_type']}' unknown to server"
        for nid, node in workflow.items()
        if node.get("class_type") not in object_info
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Submission / polling
# ─────────────────────────────────────────────────────────────────────────────

def submit_workflow(workflow: dict) -> str:
    """POST the workflow to /prompt; return the prompt_id."""
    req = urllib.request.Request(
        f"{COMFY_API}/prompt",
        data=json.dumps(build_payload(workflow)).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    if resp.get("node_errors"):
        raise LocalGenerationError(f"ComfyUI node errors: {str(resp['node_errors'])[:800]}")
    return resp["prompt_id"]


def wait_for_completion(prompt_id: str, timeout: int = GENERATION_TIMEOUT_SECONDS) -> dict:
    """Poll /history/<id> until the job completes; return the history entry."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as r:
                hist = json.loads(r.read())
        except (urllib.error.URLError, OSError):
            time.sleep(5)
            continue
        entry = hist.get(prompt_id)
        if entry and entry.get("status", {}).get("completed"):
            status = entry["status"]
            if status.get("status_str") == "success":
                return entry
            err = ""
            for msg in status.get("messages", []):
                if msg[0] == "execution_error":
                    err = msg[1].get("exception_message", "")[:600]
            raise LocalGenerationError(f"ComfyUI job failed: {status.get('status_str')} {err}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise LocalGenerationError(f"ComfyUI job {prompt_id} timed out after {timeout}s")


def output_video_paths(history_entry: dict) -> list:
    """Extract absolute mp4 paths (under COMFY_OUTPUT_DIR) from a history entry."""
    paths = []
    for node_output in history_entry.get("outputs", {}).values():
        for group in node_output.values():
            if not isinstance(group, list):
                continue
            for item in group:
                if isinstance(item, dict) and str(item.get("filename", "")).endswith(".mp4"):
                    paths.append(
                        str(COMFY_OUTPUT_DIR / item.get("subfolder", "") / item["filename"])
                    )
    return paths


def generate_clip(
    prompt: str,
    filename_prefix: str,
    mode: str = "t2v",
    start_image: str = None,
    seed: int = DEFAULT_SEED,
    **build_kwargs,
) -> str:
    """Build, validate, submit, and wait for one clip. Returns the mp4 path
    inside /home/darshon/comfyui/output/."""
    wf = build_workflow(
        prompt, mode=mode, start_image=start_image, seed=seed,
        filename_prefix=filename_prefix, **build_kwargs,
    )
    problems = validate_workflow(wf, check_input_image=(mode == "i2v"))
    if problems:
        raise WorkflowValidationError("; ".join(problems))
    prompt_id = submit_workflow(wf)
    print(f"  Submitted to ComfyUI (prompt_id={prompt_id}), polling ", end="", flush=True)
    entry = wait_for_completion(prompt_id)
    print("done.")
    videos = output_video_paths(entry)
    if not videos:
        raise LocalGenerationError("job succeeded but produced no mp4 output")
    return videos[0]


# ─────────────────────────────────────────────────────────────────────────────
# Scene / scenario orchestration
# ─────────────────────────────────────────────────────────────────────────────

def stage_input_image(image_path: str) -> str:
    """Copy an image into ComfyUI's input/ dir; return the staged filename."""
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"start image not found: {image_path}")
    dest = COMFY_INPUT_DIR / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return src.name


def extract_last_frame(video_path: str, staged_name: str) -> str:
    """Extract the last frame of an mp4 into ComfyUI's input/ dir via ffmpeg
    (used to chain i2v clips, like the Veo extension behavior)."""
    dest = COMFY_INPUT_DIR / staged_name
    subprocess.run(
        ["ffmpeg", "-y", "-sseof", "-0.5", "-i", video_path,
         "-update", "1", "-frames:v", "1", str(dest)],
        check=True, capture_output=True,
    )
    return staged_name


def concat_clips(clip_paths: list, out_path: str) -> str:
    """Losslessly concatenate same-codec mp4 clips with ffmpeg."""
    list_file = Path(out_path).with_suffix(".txt")
    list_file.write_text("".join(f"file '{p}'\n" for p in clip_paths))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    list_file.unlink(missing_ok=True)
    return out_path


def dry_run_scene(scene_id: int, clip_prompts: list, mode: str = "t2v",
                  start_image: str = None, seed: int = DEFAULT_SEED,
                  character_lora: str = None) -> list:
    """Build and print the exact /prompt payload for every clip of a scene
    WITHOUT submitting anything. Returns the list of payload dicts."""
    payloads = []
    all_problems = []
    for i, prompt in enumerate(clip_prompts, start=1):
        staged = None
        if mode == "i2v":
            # clip 1 starts from the anchor; later clips would chain from the
            # previous clip's last frame (file created at render time).
            staged = (Path(start_image).name if i == 1 and start_image
                      else f"scene{scene_id}_clip{i}_start.png")
        wf = build_workflow(
            prompt, mode=mode, start_image=staged, seed=seed,
            filename_prefix=f"wan22/scene{scene_id}_clip{i}",
            character_lora=character_lora,
        )
        problems = validate_workflow(wf) + check_server_node_types(wf)
        payload = build_payload(wf)
        payloads.append(payload)
        print(f"\n{'='*60}\nSCENE {scene_id} CLIP {i} — POST {COMFY_API}/prompt\n{'='*60}")
        print(json.dumps(payload, indent=2))
        if problems:
            all_problems.extend(f"[clip {i}] {p}" for p in problems)
    print(f"\n{'-'*60}")
    if all_problems:
        print("VALIDATION PROBLEMS:")
        for p in all_problems:
            print(f"  ✗ {p}")
    else:
        print("✓ All payloads valid: node references consistent, model files "
              "present on disk, class types known to the server.")
    return payloads


def run_scenario_pipeline_local(
    scenario: dict,
    mode: str = "t2v",
    start_image: str = None,
    seed: int = DEFAULT_SEED,
    character_lora: str = None,
) -> list:
    """Local counterpart of pipeline.run_scenario_pipeline. Renders each clip
    as its own ComfyUI job, then concatenates a scene's clips into one mp4 in
    output/. Returns [{scene_id, success, output_file, error}, ...]."""
    from .prompt_builder import build_clip_prompts
    from .logging_utils import log_scene_attempt

    characters = scenario["characters"]
    visual_style = scenario["visual_style"]
    results = []

    for scene in scenario["scenes"]:
        scene_id = scene["scene_id"]
        start_time = time.time()
        clip_log_entries = []
        try:
            clip_prompts = build_clip_prompts(scene, characters, visual_style)
            print(f"\n{'─'*60}\nSCENE {scene_id} — {len(clip_prompts)} clips (local Wan2.2 {mode})\n{'─'*60}")

            staged = stage_input_image(start_image) if (mode == "i2v" and start_image) else None
            clip_paths = []
            for i, prompt in enumerate(clip_prompts, start=1):
                print(f"\n Generating clip {i}/{len(clip_prompts)}...")
                t_clip = time.time()
                clip_path = generate_clip(
                    prompt,
                    filename_prefix=f"wan22/scene{scene_id}_clip{i}",
                    mode=mode,
                    start_image=staged,
                    seed=seed,
                    character_lora=character_lora,
                )
                clip_paths.append(clip_path)
                clip_log_entries.append({
                    "clip_id": i,
                    "attempt_number": 1,
                    "eval_passed": None,
                    "video_duration_seconds": round(DEFAULT_LENGTH / DEFAULT_FPS, 2),
                    "estimated_cost_usd": 0.0,  # local GPU
                    "generation_time": round(time.time() - t_clip, 1),
                    "eval_report_path": None,
                    "error": None,
                    "prompt": prompt,
                })
                if mode == "i2v":
                    # chain: next clip starts from this clip's last frame
                    staged = extract_last_frame(clip_path, f"scene{scene_id}_clip{i+1}_start.png")

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            OUTPUT_DIR.mkdir(exist_ok=True)
            final_path = str(OUTPUT_DIR / f"scene{scene_id}_final_local_{ts}.mp4")
            if len(clip_paths) == 1:
                shutil.copy2(clip_paths[0], final_path)
            else:
                concat_clips(clip_paths, final_path)

            wall = time.time() - start_time
            log_scene_attempt(
                scene_id=scene_id,
                scene_attempt=1,
                model_key=f"{MODEL_KEY_LOCAL}-{mode}",
                reference_images=[start_image] if start_image else [],
                success=True,
                eval_passed=None,
                total_time_seconds=wall,
                clips=clip_log_entries,
                fallback_cost_usd=0.0,
                final_output_file=final_path,
                final_video_duration_seconds=round(len(clip_paths) * DEFAULT_LENGTH / DEFAULT_FPS, 1),
                final_file_size_mb=round(os.path.getsize(final_path) / (1024 * 1024), 2),
            )
            print(f"\nScene {scene_id} complete in {wall:.0f}s\nFinal video: {final_path}")
            results.append({"scene_id": scene_id, "success": True,
                            "output_file": final_path, "error": None})
        except Exception as e:
            log_scene_attempt(
                scene_id=scene_id,
                scene_attempt=1,
                model_key=f"{MODEL_KEY_LOCAL}-{mode}",
                reference_images=[start_image] if start_image else [],
                success=False,
                eval_passed=None,
                total_time_seconds=time.time() - start_time,
                clips=clip_log_entries,
                error=str(e),
            )
            results.append({"scene_id": scene_id, "success": False,
                            "output_file": None, "error": str(e)})

    return results
