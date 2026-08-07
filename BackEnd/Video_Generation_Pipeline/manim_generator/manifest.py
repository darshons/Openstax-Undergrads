"""Branch-graph manifest for a generated scenario.

The manifest is the contract between this generator and the (future)
interactive player: every scene clip is listed with its verbatim routing, and
each decision point maps its choices to the clip that plays when the learner
picks it. `golden_path` is the correct-answers-only traversal used for the
stitched preview video.
"""

from .script_adapter import ScenarioSpec


def compute_golden_path(spec: ScenarioSpec) -> list[int]:
    """Scene ids along the correct path: trunk scenes in script order, with
    each decision point's resolution scene inserted after the decision point's
    last introduction scene on the trunk."""
    trunk = spec.trunk_scenes
    trunk_index = {s.scene_id: i for i, s in enumerate(trunk)}

    # A DP is "attached" after the last trunk scene that introduces it (via
    # routes_to or associated_introduction_scene_id).
    attach_after: dict[int, int] = {}  # trunk position -> dp_id
    for dp in spec.decision_points:
        intro_positions = [
            trunk_index[s.scene_id]
            for s in trunk
            if s.routes_to_dp_id == dp.decision_point_id
        ]
        if dp.intro_scene_id in trunk_index:
            intro_positions.append(trunk_index[dp.intro_scene_id])
        if intro_positions:
            attach_after[max(intro_positions)] = dp.decision_point_id

    dps_by_id = {dp.decision_point_id: dp for dp in spec.decision_points}
    path: list[int] = []
    for i, scene in enumerate(trunk):
        path.append(scene.scene_id)
        dp_id = attach_after.get(i)
        if dp_id is not None:
            resolution = dps_by_id[dp_id].correct_choice.routes_to_scene
            if resolution is not None:
                path.append(resolution)
    return path


def build_manifest(
    spec: ScenarioSpec,
    request_id: str,
    scene_files: dict[int, str],
    scene_durations: dict[int, float],
    golden_path_video: str | None,
) -> dict:
    golden_path = compute_golden_path(spec)
    return {
        "request_id": request_id,
        "title": spec.title,
        "learning_goal": spec.learning_goal,
        "scenes": [
            {
                "scene_id": s.scene_id,
                "type": s.scene_type,
                "file": scene_files.get(s.scene_id),
                "duration_actual_s": scene_durations.get(s.scene_id),
                "routes_to": s.routes_to,
            }
            for s in spec.scenes
        ],
        "decision_points": [
            {
                "decision_point_id": dp.decision_point_id,
                "question_text": dp.question_text,
                "after_scene_id": dp.intro_scene_id,
                "choices": [
                    {
                        "choice_id": c.choice_id,
                        "text": c.text,
                        "is_correct": c.is_correct,
                        "misconception": c.misconception,
                        "routes_to_scene": c.routes_to_scene,
                        "clip_file": (
                            scene_files.get(c.routes_to_scene)
                            if c.routes_to_scene is not None
                            else None
                        ),
                    }
                    for c in dp.choices
                ],
            }
            for dp in spec.decision_points
        ],
        "golden_path": golden_path,
        "golden_path_video": golden_path_video,
    }


def validate_manifest_against_script(manifest: dict, script: dict) -> list[str]:
    """Verification helper: the manifest's graph must be isomorphic to the
    script's. Returns a list of discrepancies (empty = consistent)."""
    problems = []
    script_scenes = {s["scene_id"]: s for s in script["scenes"]}
    manifest_scenes = {s["scene_id"]: s for s in manifest["scenes"]}

    if set(script_scenes) != set(manifest_scenes):
        problems.append(
            f"Scene id mismatch: script={sorted(script_scenes)} "
            f"manifest={sorted(manifest_scenes)}"
        )
    for sid in set(script_scenes) & set(manifest_scenes):
        if script_scenes[sid].get("routes_to") != manifest_scenes[sid]["routes_to"]:
            problems.append(f"Scene {sid}: routes_to differs from script")

    script_dps = {
        d["decision_point_id"]: d for d in script.get("decision_points") or []
    }
    manifest_dps = {d["decision_point_id"]: d for d in manifest["decision_points"]}
    if set(script_dps) != set(manifest_dps):
        problems.append(
            f"Decision point mismatch: script={sorted(script_dps)} "
            f"manifest={sorted(manifest_dps)}"
        )
    for dp_id in set(script_dps) & set(manifest_dps):
        s_choices = {c["choice_id"]: c for c in script_dps[dp_id]["choices"]}
        m_choices = {c["choice_id"]: c for c in manifest_dps[dp_id]["choices"]}
        if set(s_choices) != set(m_choices):
            problems.append(f"DP {dp_id}: choice ids differ")
            continue
        for cid in s_choices:
            for key in ("is_correct", "routes_to_scene"):
                if s_choices[cid].get(key) != m_choices[cid].get(key):
                    problems.append(f"DP {dp_id} choice {cid}: {key} differs")
    return problems
