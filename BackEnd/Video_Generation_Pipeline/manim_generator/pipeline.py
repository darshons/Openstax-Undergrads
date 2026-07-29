"""Orchestrate one scenario: asset kit -> per-scene plan/code/render/repair ->
manifest + golden-path preview.

Scenes RENDER strictly serially — parallel manim subprocesses deadlock (hard-won
TheoremExplainAgent lesson). Planning calls happen inline with each scene for
simplicity; the render dominates wall-clock anyway.

``render_scene`` is the per-scene unit, shared by the full run and by the
single-scene regeneration path (``regenerate_scene``) the API exposes so users
can edit a scene's plan or code and re-render just that scene against the
already-frozen asset kit.
"""

import json
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
from .llm_client import make_client
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
    """Resolve the Kokoro TTS model files. Order: explicit env vars, then
    auto-discovery in common local install dirs. If nothing is found the run
    still proceeds — kokoro_voiceover.py degrades to silent audio clips of the
    estimated speech duration, so the silent-video path always works."""
    import glob

    model_path = os.environ.get("KOKORO_MODEL_PATH", "models/kokoro-v0_19.onnx")
    voices_path = os.environ.get("KOKORO_VOICES_PATH", "models/voices.bin")
    if os.path.exists(model_path) and os.path.exists(voices_path):
        return

    for candidate_dir in (
        os.path.expanduser("~/kokoro-tts"),
        os.path.expanduser("~/kokoro"),
        os.path.join(PACKAGE_DIR, "models"),
    ):
        onnx = sorted(glob.glob(os.path.join(candidate_dir, "kokoro*.onnx")))
        voices = sorted(glob.glob(os.path.join(candidate_dir, "voices*.bin")))
        if onnx and voices:
            os.environ["KOKORO_MODEL_PATH"] = onnx[-1]
            os.environ["KOKORO_VOICES_PATH"] = voices[-1]
            print(f"[kokoro] auto-discovered model files in {candidate_dir}")
            return

    print(
        "[kokoro] TTS model files not found (set KOKORO_MODEL_PATH / "
        "KOKORO_VOICES_PATH to enable narration) — scenes will render with "
        "SILENT voiceover tracks of the estimated speech duration"
    )


def render_scene(
    spec,
    scene,
    out_dir: str,
    assets_path: str,
    asset_api: str,
    background: str,
    codegen: CodeGenerator,
    renderer: VideoRenderer,
    client: GeminiClient,
    banned: list[str],
    status: RunStatus,
    plan_override: str | None = None,
    code_override: str | None = None,
) -> tuple[str | None, float | None]:
    """Plan, generate, render, repair and grid-critique ONE scene against an
    already-frozen asset kit. Returns (final_video_path, duration_s), or
    (None, None) if the scene never rendered.

    ``plan_override`` / ``code_override`` let a caller supply user-edited
    content: a plan skips the planner call, and code additionally skips
    codegen so the user's own Manim source is what gets rendered.

    Raises on unexpected failures; the caller decides whether that kills the
    whole run or just this scene.
    """
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

    plan = plan_override if plan_override is not None else plan_scene(spec, scene, asset_api, client)
    occupancy = extract_occupancy_table(plan)
    with open(os.path.join(scene_dir, "plan.txt"), "w", encoding="utf-8") as f:
        f.write(plan)

    if code_override is not None:
        code = code_override
    else:
        code, _ = codegen.generate_scene_code(
            build_code_prompt(spec, scene, plan, asset_api),
            label=f"scene_{scene.scene_id}_code",
        )
    scene_name = f"Scene{scene.scene_id}"

    # Continue the version series rather than restarting at v0, so a regenerated
    # scene's history sits alongside the original attempts instead of overwriting them.
    scene_version = _next_scene_version(code_dir, scene.scene_id)

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
        return None, None

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
    duration = renderer.probe_duration(final_path)
    return final_path, round(duration, 2) if duration else None


def _next_scene_version(code_dir: str, scene_id: int) -> int:
    """Highest existing vN for this scene + 1 (0 when the scene is untouched)."""
    prefix, best = f"scene_{scene_id}_v", -1
    if os.path.isdir(code_dir):
        for name in os.listdir(code_dir):
            if name.startswith(prefix) and name.endswith(".py"):
                try:
                    best = max(best, int(name[len(prefix):-len(".py")]))
                except ValueError:
                    continue
    return best + 1


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

    client = make_client(model)
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

    # Persist the inputs a later single-scene regeneration needs. The asset kit is
    # frozen for the scenario's lifetime, so a regen reloads it from disk rather
    # than paying for (and risking a different) kit.
    _write_run_context(out_dir, script, request_id, quality, model)

    # ---- Stage: per-scene loop (SERIAL renders) ----
    scene_files: dict[int, str] = {}
    scene_durations: dict[int, float] = {}
    total = len(spec.scenes)

    for i, scene in enumerate(spec.scenes, start=1):
        status.set_state(f"scene_{i}_of_{total}")
        try:
            final_path, duration = render_scene(
                spec, scene, out_dir, assets_path, asset_api, background,
                codegen, renderer, client, banned, status,
            )
            if final_path is None:
                status.scene_failed(scene.scene_id, "render failed after ScopeRefine repairs")
                status.log_event(event="scene_failed", scene_id=scene.scene_id)
                continue

            scene_files[scene.scene_id] = final_path
            if duration:
                scene_durations[scene.scene_id] = duration
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
    _write_manifest(out_dir, manifest)
    status.finish(manifest)
    return manifest


# ---------------------------------------------------------------------------
# Single-scene regeneration
# ---------------------------------------------------------------------------

RUN_CONTEXT_NAME = "run_context.json"


def _write_run_context(out_dir: str, script: dict, request_id: str, quality: str, model: str):
    """Snapshot what a regen needs: the script (source of truth for the spec)
    plus the render settings, so a re-render matches the original run."""
    context = {
        "request_id": request_id,
        "script": script,
        "quality": quality,
        "model": model,
    }
    tmp = os.path.join(out_dir, RUN_CONTEXT_NAME + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)
    os.replace(tmp, os.path.join(out_dir, RUN_CONTEXT_NAME))


def _write_manifest(out_dir: str, manifest: dict):
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def read_run_context(out_dir: str) -> dict | None:
    path = os.path.join(out_dir, RUN_CONTEXT_NAME)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def regenerate_scene(
    request_id: str,
    scene_id: int,
    out_root: str = "output",
    plan_override: str | None = None,
    code_override: str | None = None,
    script_override: dict | None = None,
    restitch: bool = True,
) -> dict:
    """Re-render ONE scene of an existing run against its frozen asset kit.

    This is the user-control path: the frontend hands back an edited plan, edited
    Manim source, or an edited script, and only that scene is rebuilt — the asset
    kit (and therefore cross-scene character consistency) is untouched.

    Must run on the same single worker as full runs: parallel manim subprocesses
    deadlock. Returns the refreshed manifest.
    """
    out_dir = os.path.abspath(os.path.join(out_root, request_id))
    context = read_run_context(out_dir)
    if context is None:
        raise FileNotFoundError(
            f"No run context for request_id {request_id!r} — a scene can only be "
            "regenerated after a full run has frozen its asset kit."
        )

    script = script_override if script_override is not None else context["script"]
    spec = adapt(script)
    scene = spec.scenes_by_id.get(scene_id)
    if scene is None:
        raise ValueError(f"Scene {scene_id} is not part of run {request_id!r}")

    assets_path = os.path.join(out_dir, "asset_kit", "assets.py")
    if not os.path.exists(assets_path):
        raise FileNotFoundError(f"Frozen asset kit missing for run {request_id!r}")

    quality = context.get("quality", "m")
    model = context.get("model", DEFAULT_MODEL)
    client = make_client(model)
    codegen = CodeGenerator(client)
    renderer = VideoRenderer(quality=quality)
    banned = [l.strip() for l in load_prompt("banned_reasonings").splitlines() if l.strip()]

    asset_api = extract_asset_api(assets_path)
    background = extract_background_color(assets_path)
    voice_map = extract_voice_map(assets_path)
    for character in spec.characters:
        if character.character_id in voice_map:
            character.voice = voice_map[character.character_id]

    status = RunStatus(out_dir, resume=True)
    status.set_state(f"regenerating_scene_{scene_id}")
    status.log_event(
        event="scene_regen_started", scene_id=scene_id,
        edited_plan=plan_override is not None,
        edited_code=code_override is not None,
        edited_script=script_override is not None,
    )

    try:
        final_path, duration = render_scene(
            spec, scene, out_dir, assets_path, asset_api, background,
            codegen, renderer, client, banned, status,
            plan_override=plan_override, code_override=code_override,
        )
    except Exception as e:
        status.scene_failed(scene_id, traceback.format_exc(limit=3))
        status.log_event(event="scene_regen_error", scene_id=scene_id,
                         error=traceback.format_exc())
        status.set_state("done")
        raise RuntimeError(f"Scene {scene_id} regeneration failed: {e}") from e

    if final_path is None:
        status.scene_failed(scene_id, "render failed after ScopeRefine repairs")
        status.log_event(event="scene_regen_failed", scene_id=scene_id)
    else:
        status.scene_done(scene_id, final_path)
        status.log_event(event="scene_regen_done", scene_id=scene_id)

    if script_override is not None:
        _write_run_context(out_dir, script, request_id, quality, model)

    # Rebuild the manifest from whatever is now on disk so the edited scene's new
    # video and duration are what the frontend sees.
    scene_files, scene_durations = _collect_scene_files(out_dir, spec, renderer)

    golden_video = None
    golden_path = compute_golden_path(spec)
    if restitch and golden_path and all(sid in scene_files for sid in golden_path):
        status.set_state("stitching")
        golden_video = os.path.join(out_dir, "golden_path.mp4")
        renderer.stitch([scene_files[sid] for sid in golden_path], golden_video)
    elif restitch:
        missing = [sid for sid in golden_path if sid not in scene_files]
        status.log_event(event="golden_path_skipped", missing_scenes=missing)

    manifest = build_manifest(spec, request_id, scene_files, scene_durations, golden_video)
    _write_manifest(out_dir, manifest)
    status.finish(manifest)
    return manifest


def _collect_scene_files(out_dir: str, spec, renderer: VideoRenderer):
    """Scan the run dir for finished per-scene videos. Durations are re-probed
    from the files themselves, so an edited scene's new length is picked up."""
    scene_files: dict[int, str] = {}
    scene_durations: dict[int, float] = {}
    for scene in spec.scenes:
        path = os.path.join(
            out_dir, "scenes", f"scene_{scene.scene_id}", f"scene_{scene.scene_id}.mp4"
        )
        if os.path.exists(path):
            scene_files[scene.scene_id] = path
            duration = renderer.probe_duration(path)
            if duration:
                scene_durations[scene.scene_id] = round(duration, 2)
    return scene_files, scene_durations
