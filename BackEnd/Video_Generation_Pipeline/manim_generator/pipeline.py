"""Orchestrate one scenario: asset kit -> per-scene plan/code/render/repair ->
manifest + golden-path preview.

Scenes RENDER strictly serially — parallel manim subprocesses deadlock (hard-won
TheoremExplainAgent lesson). Planning calls happen inline with each scene for
simplicity; the render dominates wall-clock anyway.
"""

import os
import shutil
import traceback

from .asset_kit import (
    extract_asset_api,
    extract_background_color,
    extract_voice_map,
    generate_asset_kit,
)
from .code_generator import CodeGenerator, load_prompt
from .gemini_client import DEFAULT_MODEL, GeminiClient
from .grid_overlay import overlay_grid
from .logging_utils import RunStatus
from .manifest import build_manifest, compute_golden_path
from .prompt_builder import build_code_prompt
from .repair import scope_refine_repair
from .scene_planner import extract_occupancy_table, plan_scene
from .script_adapter import adapt
from .video_renderer import VideoRenderer, truncate_error_log

MAX_SCENE_REPAIRS = 7   # escalating repair rounds (each round runs line->block->full)
MAX_CRITIC_ROUNDS = 2   # grid-critic re-render rounds after a successful render
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def _write_manim_cfg(code_dir: str, background_color: str):
    """Pin the background at render time: the LLM cannot be trusted to emit a
    background mobject in every code path, so the .cfg guarantees it."""
    with open(os.path.join(code_dir, "manim.cfg"), "w", encoding="utf-8") as f:
        f.write(f"[CLI]\nbackground_color = {background_color}\n")


def _check_kokoro_env():
    model_path = os.environ.get("KOKORO_MODEL_PATH", "models/kokoro-v0_19.onnx")
    voices_path = os.environ.get("KOKORO_VOICES_PATH", "models/voices.bin")
    missing = [p for p in (model_path, voices_path) if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            "Kokoro TTS model files not found: "
            + ", ".join(missing)
            + " — set KOKORO_MODEL_PATH / KOKORO_VOICES_PATH (absolute paths) in the environment or .env"
        )


def run_scenario_pipeline(
    script: dict,
    request_id: str,
    out_root: str = "output",
    quality: str = "m",
    model: str = DEFAULT_MODEL,
    stitch_golden: bool = True,
) -> dict:
    """Generate all clips for one scenario script. Returns the manifest dict.
    Writes status.json continuously for the polling API."""
    out_dir = os.path.abspath(os.path.join(out_root, request_id))
    status = RunStatus(out_dir)
    try:
        return _run(script, request_id, out_dir, quality, model, stitch_golden, status)
    except Exception as e:
        status.fail(f"{type(e).__name__}: {e}")
        status.log_event(event="pipeline_error", error=traceback.format_exc())
        raise


def _run(script, request_id, out_dir, quality, model, stitch_golden, status) -> dict:
    _check_kokoro_env()
    spec = adapt(script)
    for warning in spec.warnings:
        status.log_event(event="validation_warning", detail=warning)

    client = GeminiClient(model=model)
    codegen = CodeGenerator(client)
    renderer = VideoRenderer(quality=quality)
    banned = [l.strip() for l in load_prompt("banned_reasonings").splitlines() if l.strip()]

    # ---- Stage: asset kit (once per scenario, then frozen) ----
    status.set_state("assets")
    kit_dir = os.path.join(out_dir, "asset_kit")
    assets_path = generate_asset_kit(spec, codegen, renderer, kit_dir, log=print)
    asset_api = extract_asset_api(assets_path)
    background = extract_background_color(assets_path)
    voice_map = extract_voice_map(assets_path)
    for character in spec.characters:
        if character.character_id in voice_map:
            character.voice = voice_map[character.character_id]
    status.log_event(event="asset_kit_frozen", background=background, voice_map=voice_map)

    # ---- Stage: per-scene loop (SERIAL renders) ----
    scene_files: dict[int, str] = {}
    scene_durations: dict[int, float] = {}
    total = len(spec.scenes)

    for i, scene in enumerate(spec.scenes, start=1):
        status.set_state(f"scene_{i}_of_{total}")
        scene_dir = os.path.join(out_dir, "scenes", f"scene_{scene.scene_id}")
        code_dir = os.path.join(scene_dir, "code")
        media_dir = os.path.join(scene_dir, "media")
        os.makedirs(code_dir, exist_ok=True)

        # the scene's import neighborhood: frozen assets + TTS service + cfg
        shutil.copy(assets_path, os.path.join(code_dir, "assets.py"))
        shutil.copy(
            os.path.join(PACKAGE_DIR, "kokoro_voiceover.py"),
            os.path.join(code_dir, "kokoro_voiceover.py"),
        )
        _write_manim_cfg(code_dir, background)

        try:
            plan = plan_scene(spec, scene, asset_api, client)
            occupancy = extract_occupancy_table(plan)
            with open(os.path.join(scene_dir, "plan.txt"), "w", encoding="utf-8") as f:
                f.write(plan)

            code, _ = codegen.generate_scene_code(
                build_code_prompt(spec, scene, plan, asset_api),
                label=f"scene_{scene.scene_id}_code",
            )
            scene_name = f"Scene{scene.scene_id}"
            scene_version = 0

            def write_version(source: str) -> str:
                nonlocal scene_version
                path = os.path.join(code_dir, f"scene_{scene.scene_id}_v{scene_version}.py")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(source)
                scene_version += 1
                return path

            # ---- render + ScopeRefine repair loop ----
            code_path = write_version(code)
            ok, stderr = renderer.render(code_path, media_dir, scene_name=scene_name)
            for round_i in range(MAX_SCENE_REPAIRS):
                if ok:
                    break
                error = truncate_error_log(stderr, code_path)
                with open(code_path.replace(".py", "_error.log"), "w", encoding="utf-8") as f:
                    f.write(stderr)
                status.log_event(
                    event="render_failed", scene_id=scene.scene_id,
                    round=round_i + 1, error_tail=error.splitlines()[-1] if error else "",
                )
                code_path = write_version(code)
                code, ok, stderr = scope_refine_repair(
                    scene.scene_id, code, stderr, plan, code_path,
                    codegen, renderer, media_dir, scene_name, log=print,
                )

            if not ok:
                status.scene_failed(scene.scene_id, "render failed after ScopeRefine repairs")
                status.log_event(event="scene_failed", scene_id=scene.scene_id)
                continue

            video_path = renderer.find_scene_video(media_dir, code_path)
            status.log_event(event="scene_rendered", scene_id=scene.scene_id, versions=scene_version)

            # ---- forced grid critic (>=1 pass; TEA's critic never fired on
            # first-try-clean scenes, so layout defects shipped unexamined) ----
            for critic_round in range(MAX_CRITIC_ROUNDS):
                snap = renderer.snapshot(
                    video_path, os.path.join(scene_dir, f"snapshot_v{critic_round}.png")
                )
                grid_img = overlay_grid(snap, os.path.join(scene_dir, f"grid_v{critic_round}.png"),
                                        return_type="image")
                new_code, response = codegen.visual_self_reflection_grid(code, grid_img, occupancy)
                if "<LGTM>" in new_code or any(m in response for m in banned):
                    status.log_event(event="grid_critic_pass", scene_id=scene.scene_id,
                                     round=critic_round + 1, verdict="clean")
                    break
                status.log_event(event="grid_critic_fix", scene_id=scene.scene_id,
                                 round=critic_round + 1)
                code = new_code
                code_path = write_version(code)
                ok, stderr = renderer.render(code_path, media_dir, scene_name=scene_name)
                if not ok:
                    # critic's fix broke the render; keep the last good video
                    status.log_event(event="grid_critic_regressed", scene_id=scene.scene_id)
                    break
                video_path = renderer.find_scene_video(media_dir, code_path)

            final_path = os.path.join(scene_dir, f"scene_{scene.scene_id}.mp4")
            shutil.copy(video_path, final_path)
            scene_files[scene.scene_id] = final_path
            duration = renderer.probe_duration(final_path)
            if duration:
                scene_durations[scene.scene_id] = round(duration, 2)
            status.scene_done(scene.scene_id, final_path)

        except Exception:
            status.scene_failed(scene.scene_id, traceback.format_exc(limit=3))
            status.log_event(event="scene_error", scene_id=scene.scene_id,
                             error=traceback.format_exc())

    # ---- Stage: golden-path preview + manifest ----
    golden_video = None
    golden_path = compute_golden_path(spec)
    if stitch_golden and all(sid in scene_files for sid in golden_path):
        status.set_state("stitching")
        golden_video = os.path.join(out_dir, "golden_path.mp4")
        renderer.stitch([scene_files[sid] for sid in golden_path], golden_video)
    elif stitch_golden:
        missing = [sid for sid in golden_path if sid not in scene_files]
        status.log_event(event="golden_path_skipped", missing_scenes=missing)

    manifest = build_manifest(spec, request_id, scene_files, scene_durations, golden_video)
    manifest_path = os.path.join(out_dir, "manifest.json")
    import json
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    status.finish(manifest)
    return manifest
