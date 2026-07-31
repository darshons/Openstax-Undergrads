"""Status + generation logging for one scenario run.

status.json is the polling contract for the API layer: the pipeline rewrites
it after every stage transition, so GET /manim_video_status is a pure file
read. generation_log.jsonl accumulates per-event records (attempts, repairs,
critic verdicts) for debugging and cross-run comparisons.
"""

import json
import os
import time


class RunStatus:
    def __init__(self, out_dir: str, resume: bool = False):
        """``resume=True`` reloads an existing status.json instead of resetting
        it — used when regenerating a single scene of a finished run, where
        wiping completed_scenes would strip every other scene from the UI."""
        self.path = os.path.join(out_dir, "status.json")
        self.log_path = os.path.join(out_dir, "generation_log.jsonl")
        os.makedirs(out_dir, exist_ok=True)
        self._state = None
        if resume and os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    loaded.setdefault("completed_scenes", {})
                    loaded.setdefault("failed_scenes", {})
                    loaded.setdefault("manifest", None)
                    loaded.setdefault("error", None)
                    self._state = loaded
            except (json.JSONDecodeError, OSError):
                self._state = None  # unreadable status: fall back to a fresh one
        if self._state is None:
            self._state = {
                "state": "queued",
                "completed_scenes": {},
                "failed_scenes": {},
                "manifest": None,
                "error": None,
            }
        self._write()

    def _write(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)
        os.replace(tmp, self.path)

    def set_state(self, state: str):
        self._state["state"] = state
        self._write()

    def scene_done(self, scene_id: int, video_path: str):
        self._state["completed_scenes"][str(scene_id)] = video_path
        # a scene that now renders is no longer failed (regeneration case)
        self._state["failed_scenes"].pop(str(scene_id), None)
        self._write()

    def scene_failed(self, scene_id: int, error: str):
        self._state["failed_scenes"][str(scene_id)] = error
        self._state["completed_scenes"].pop(str(scene_id), None)
        self._write()

    def finish(self, manifest: dict):
        # "done" must mean every scene rendered. Reporting it while scenes are in
        # failed_scenes makes the UI show a green finish with missing videos, since
        # the client keys off state alone.
        self._state["manifest"] = manifest
        if not self._state["failed_scenes"]:
            self._state["state"] = "done"
        elif self._state["completed_scenes"]:
            self._state["state"] = "partial"
        else:
            self._state["state"] = "error"
            self._state["error"] = "every scene failed to render"
        self._write()

    def fail(self, error: str):
        self._state["error"] = error
        self._state["state"] = "error"
        self._write()

    def log_event(self, **event):
        event["t"] = round(time.time(), 2)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
