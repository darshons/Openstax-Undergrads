"""Inventory of a run's inspectable intermediates, for the frontend.

The Manim pipeline writes a lot the user never saw: each scene's plan, every
version of its generated Manim source, the render error logs, the grid-critic
snapshots, and the frozen asset kit. The Veo pipeline exposes its intermediates
(script, background, characters, opening frames) so the user can review and
regenerate them; this module is the equivalent read model for Manim.

Paths are returned relative to the run directory. Callers resolve them through
``resolve_asset_path``, which refuses anything escaping the run — the assets
live under the system temp dir and must not become a way to read the filesystem.
"""

import os

from .pipeline import RUN_CONTEXT_NAME

# Extensions we are willing to hand back, by asset kind.
_TEXT_SUFFIXES = (".txt", ".py", ".log", ".json", ".jsonl", ".cfg")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
_VIDEO_SUFFIXES = (".mp4",)

SERVE_SUFFIXES = _TEXT_SUFFIXES + _IMAGE_SUFFIXES + _VIDEO_SUFFIXES

_KIND_BY_SUFFIX = {
    **{s: "text" for s in _TEXT_SUFFIXES},
    **{s: "image" for s in _IMAGE_SUFFIXES},
    **{s: "video" for s in _VIDEO_SUFFIXES},
}

# Internal bookkeeping the UI has no use for.
_HIDDEN_NAMES = {"status.json.tmp", RUN_CONTEXT_NAME + ".tmp"}


def asset_kind(name: str) -> str:
    return _KIND_BY_SUFFIX.get(os.path.splitext(name)[1].lower(), "other")


def _entry(run_dir: str, abs_path: str, role: str) -> dict:
    rel = os.path.relpath(abs_path, run_dir)
    return {
        "path": rel.replace(os.sep, "/"),
        "name": os.path.basename(abs_path),
        "role": role,
        "kind": asset_kind(abs_path),
        "size_bytes": os.path.getsize(abs_path),
    }


def _listdir(path: str) -> list[str]:
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _scene_version(name: str) -> tuple:
    """Sort scene_N_vK.py by K rather than lexically (v10 after v9)."""
    stem = os.path.splitext(name)[0]
    _, sep, tail = stem.rpartition("_v")
    return (int(tail), name) if sep and tail.isdigit() else (-1, name)


def list_run_assets(run_dir: str) -> dict:
    """Enumerate the intermediates of one run, grouped for the UI."""
    if not os.path.isdir(run_dir):
        raise FileNotFoundError(f"No such run directory: {run_dir}")

    run_level = []
    for name in _listdir(run_dir):
        abs_path = os.path.join(run_dir, name)
        if os.path.isfile(abs_path) and name not in _HIDDEN_NAMES:
            run_level.append(_entry(run_dir, abs_path, role="run"))

    kit_dir = os.path.join(run_dir, "asset_kit")
    asset_kit = [
        _entry(run_dir, os.path.join(kit_dir, name), role="asset_kit")
        for name in _listdir(kit_dir)
        if os.path.isfile(os.path.join(kit_dir, name))
        and name.endswith(SERVE_SUFFIXES)
    ]

    scenes = []
    scenes_root = os.path.join(run_dir, "scenes")
    for scene_name in _listdir(scenes_root):
        scene_dir = os.path.join(scenes_root, scene_name)
        if not os.path.isdir(scene_dir):
            continue

        scene_id = None
        if scene_name.startswith("scene_") and scene_name[len("scene_"):].isdigit():
            scene_id = int(scene_name[len("scene_"):])

        video = None
        plan = None
        artifacts = []
        for name in _listdir(scene_dir):
            abs_path = os.path.join(scene_dir, name)
            if not os.path.isfile(abs_path) or not name.endswith(SERVE_SUFFIXES):
                continue
            entry = _entry(run_dir, abs_path, role="scene")
            if name == f"{scene_name}.mp4":
                video = entry
            elif name == "plan.txt":
                plan = entry
            else:
                artifacts.append(entry)  # snapshot_v*.png / grid_v*.png

        code_dir = os.path.join(scene_dir, "code")
        code_versions, error_logs = [], []
        for name in sorted(_listdir(code_dir), key=_scene_version):
            abs_path = os.path.join(code_dir, name)
            if not os.path.isfile(abs_path):
                continue
            # assets.py / kokoro_voiceover.py are copies of shared files, not
            # this scene's generated source — skip them.
            if name.endswith(".py") and name.startswith(f"{scene_name}_v"):
                code_versions.append(_entry(run_dir, abs_path, role="scene_code"))
            elif name.endswith("_error.log"):
                error_logs.append(_entry(run_dir, abs_path, role="scene_error"))

        scenes.append({
            "scene_id": scene_id,
            "video": video,
            "plan": plan,
            "code_versions": code_versions,
            "latest_code": code_versions[-1] if code_versions else None,
            "error_logs": error_logs,
            "artifacts": artifacts,
        })

    scenes.sort(key=lambda s: (s["scene_id"] is None, s["scene_id"]))
    return {"run": run_level, "asset_kit": asset_kit, "scenes": scenes}


def resolve_asset_path(run_dir: str, rel_path: str) -> str:
    """Resolve a caller-supplied relative path inside ``run_dir``.

    Confined deliberately: the caller controls this string, so anything that
    escapes the run directory (``..``, an absolute path, a symlink pointing
    out) is rejected rather than served.
    """
    if not rel_path or os.path.isabs(rel_path) or "\x00" in rel_path:
        raise ValueError("Invalid asset path")

    run_root = os.path.realpath(run_dir)
    target = os.path.realpath(os.path.join(run_root, rel_path))
    if target != run_root and not target.startswith(run_root + os.sep):
        raise ValueError("Asset path escapes the run directory")
    if not os.path.isfile(target):
        raise FileNotFoundError(rel_path)
    if not target.endswith(SERVE_SUFFIXES):
        raise ValueError(f"Refusing to serve {os.path.basename(target)}")
    return target


MEDIA_TYPES = {
    ".txt": "text/plain; charset=utf-8",
    ".py": "text/plain; charset=utf-8",
    ".log": "text/plain; charset=utf-8",
    ".cfg": "text/plain; charset=utf-8",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
}


def media_type_for(path: str) -> str:
    return MEDIA_TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
