"""Per-scene planning: one LLM call producing the implementation contract.

Replaces TheoremExplainAgent's three-stage planning (storyboard -> technical
plan -> narration plan): the Script JSON already IS the storyboard (summary,
actions, positions, dialogue, duration), so a single call produces the beats,
the occupancy table (Code2Video: element -> grid anchor, so the visual critic
can check the render against a declared layout), and the dialogue-rendering
table with per-line TTS time budgets (Manimator: pre-estimated speech time
keeps clip length near the authored duration).
"""

from .gemini_client import GeminiClient
from .prompt_builder import build_scene_plan_prompt
from .script_adapter import Scene, ScenarioSpec

REQUIRED_SECTIONS = ("<BEATS>", "<OCCUPANCY_TABLE>", "<DIALOGUE_TABLE>")


def extract_occupancy_table(plan: str) -> str:
    start = plan.find("<OCCUPANCY_TABLE>")
    end = plan.find("</OCCUPANCY_TABLE>")
    if start != -1 and end != -1:
        return plan[start + len("<OCCUPANCY_TABLE>") : end].strip()
    return ""


def plan_scene(
    spec: ScenarioSpec,
    scene: Scene,
    asset_api: str,
    client: GeminiClient,
    max_retries: int = 2,
) -> str:
    prompt = build_scene_plan_prompt(spec, scene, asset_api)
    plan = client.generate(prompt, label=f"scene_plan_{scene.scene_id}")
    for _ in range(max_retries):
        missing = [s for s in REQUIRED_SECTIONS if s not in plan]
        if not missing:
            break
        plan = client.generate(
            prompt
            + f"\n\nYour previous plan was missing the required section(s) {missing}. "
            "Produce the complete plan again with ALL three sections.",
            label=f"scene_plan_{scene.scene_id}_retry",
        )
    return plan
