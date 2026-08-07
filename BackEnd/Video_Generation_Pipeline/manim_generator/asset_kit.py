"""Generate and freeze the per-scenario visual asset kit (assets.py).

The kit is the structural answer to cross-scene character consistency: every
scene imports the same build functions, so avatars are identical by
construction (the same reason the Veo pipeline passes reference images).
Generated once, validated by rendering its AssetLineup test scene through the
repair loop, then frozen — never regenerated during the scene loop.
"""

import ast
import os
import re

from .code_generator import CodeGenerator
from .grid_overlay import overlay_grid
from .prompt_builder import build_asset_kit_prompt, build_character_block
from .script_adapter import ScenarioSpec
from .video_renderer import VideoRenderer, truncate_error_log

ASSET_KIT_MAX_REPAIRS = 7
FALLBACK_BACKGROUND = "#0F2C4D"


def generate_asset_kit(
    spec: ScenarioSpec,
    codegen: CodeGenerator,
    renderer: VideoRenderer,
    build_dir: str,
    log=print,
) -> str:
    """Generate assets.py, prove it renders (AssetLineup), critique the lineup
    frame once against the character descriptions, and return its path. Falls
    back to a parameterized generic kit if the LLM kit never renders."""
    os.makedirs(build_dir, exist_ok=True)
    assets_path = os.path.join(build_dir, "assets.py")
    media_dir = os.path.join(build_dir, "media")

    # The whole LLM path is best-effort: any unrecoverable error (a hard API
    # failure, exhausted retries, malformed output) drops to the parameterized
    # fallback kit rather than crashing the entire scenario run.
    try:
        prompt = build_asset_kit_prompt(spec)
        code, _ = codegen.generate_scene_code(prompt, label="asset_kit")
        contract = (
            "The asset-kit module contract from the generation prompt:\n" + prompt
        )

        for attempt in range(ASSET_KIT_MAX_REPAIRS + 1):
            with open(assets_path, "w", encoding="utf-8") as f:
                f.write(code)
            ok, stderr = renderer.render(
                assets_path, media_dir, scene_name="AssetLineup"
            )
            if ok:
                log(f"[asset_kit] lineup rendered on attempt {attempt + 1}")
                _critique_lineup(
                    spec,
                    code,
                    assets_path,
                    media_dir,
                    codegen,
                    renderer,
                    build_dir,
                    log,
                )
                return assets_path
            error = truncate_error_log(stderr)
            log(
                f"[asset_kit] render failed (attempt {attempt + 1}): {error.splitlines()[-1] if error else 'unknown'}"
            )
            if attempt == ASSET_KIT_MAX_REPAIRS:
                break
            code, _ = codegen.fix_code_errors(contract, code, error)
        log("[asset_kit] LLM kit never rendered — using the parameterized fallback kit")
    except Exception as e:
        log(
            f"[asset_kit] LLM generation errored ({type(e).__name__}: {e}) — using the fallback kit"
        )

    fallback = build_fallback_kit(spec)
    with open(assets_path, "w", encoding="utf-8") as f:
        f.write(fallback)
    ok, stderr = renderer.render(assets_path, media_dir, scene_name="AssetLineup")
    if not ok:
        raise RuntimeError(
            "Fallback asset kit failed to render — environment problem, not an "
            "LLM problem:\n" + truncate_error_log(stderr)
        )
    return assets_path


def _critique_lineup(
    spec, code, assets_path, media_dir, codegen, renderer, build_dir, log
):
    """One grid-critic pass over the lineup frame; apply the fix only if it
    still renders (never let a critique regress a working kit)."""
    try:
        video = renderer.find_scene_video(media_dir, assets_path)
        if not video:
            return
        snap = renderer.snapshot(video, os.path.join(build_dir, "lineup_snapshot.png"))
        grid_img = overlay_grid(
            snap, os.path.join(build_dir, "lineup_grid.png"), return_type="image"
        )
        fixed, _ = codegen.critique_asset_lineup(
            code, grid_img, build_character_block(spec)
        )
        if "<LGTM>" in fixed:
            log("[asset_kit] lineup critique: clean")
            return
        with open(assets_path, "w", encoding="utf-8") as f:
            f.write(fixed)
        ok, _ = renderer.render(assets_path, media_dir, scene_name="AssetLineup")
        if ok:
            log("[asset_kit] lineup critique: applied a fix")
        else:
            with open(assets_path, "w", encoding="utf-8") as f:
                f.write(code)
            log("[asset_kit] lineup critique fix regressed render — reverted")
    except Exception as e:
        log(f"[asset_kit] lineup critique skipped ({type(e).__name__}: {e})")


def extract_asset_api(assets_path: str) -> str:
    """Public API summary of the frozen assets.py, injected into the scene-plan
    and code-generation prompts."""
    with open(assets_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    lines = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            args = ", ".join(a.arg for a in node.args.args)
            lines.append(f"- {node.name}({args})")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "PALETTE",
                    "VOICE_MAP",
                ):
                    try:
                        value = ast.literal_eval(node.value)
                        lines.append(f"- {target.id} = {value}")
                    except (ValueError, SyntaxError):
                        lines.append(f"- {target.id}: dict")
    return "\n".join(lines)


def extract_voice_map(assets_path: str) -> dict[str, str]:
    with open(assets_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VOICE_MAP":
                    try:
                        value = ast.literal_eval(node.value)
                        if isinstance(value, dict):
                            return value
                    except (ValueError, SyntaxError):
                        pass
    return {}


def extract_background_color(assets_path: str) -> str:
    """PALETTE['background'], for pinning manim.cfg's background_color."""
    with open(assets_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PALETTE":
                    try:
                        palette = ast.literal_eval(node.value)
                        color = palette.get("background", FALLBACK_BACKGROUND)
                        if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color)):
                            return color
                    except (ValueError, SyntaxError):
                        pass
    return FALLBACK_BACKGROUND


# ---------------------------------------------------------------------------
# Fallback kit: a minimal DIAGRAM style kit (palette, grid, title/caption/label/
# emphasis helpers) so a broken LLM generation can never hard-block a run. No
# human figures — this pipeline renders diagrams, not characters.
# ---------------------------------------------------------------------------


def build_fallback_kit(spec: ScenarioSpec) -> str:
    voice_map = ",\n".join(
        f'    "{c.character_id}": "{c.voice}"' for c in spec.characters
    )

    return f"""from manim import *

PALETTE = {{
    "background": "{FALLBACK_BACKGROUND}",
    "primary": "#4E9AF1",
    "secondary": "#F1A54E",
    "accent": "#F1D24E",
    "correct": "#5FBF77",
    "incorrect": "#E2703A",
    "text": "#F5F7FA",
    "muted": "#9AA7B4",
}}

VOICE_MAP = {{
    "narrator": "af_sarah",
{voice_map}
}}


_GRID_COLS = {{"1": -5.9, "2": -3.6, "3": -1.2, "4": 1.2, "5": 3.6, "6": 5.9}}
_GRID_ROWS = {{"A": 3.3, "B": 2.0, "C": 0.7, "D": -0.7, "E": -2.0, "F": -3.3}}


def grid_to_point(cell: str):
    \"\"\"Convert a 6x6 grid cell ("C2") or range ("C2-E3") to a Manim point.\"\"\"
    cells = cell.replace(" ", "").split("-")
    xs, ys = [], []
    for c in cells:
        row, col = c[0].upper(), c[1:]
        ys.append(_GRID_ROWS.get(row, 0.0))
        xs.append(_GRID_COLS.get(col, 0.0))
    return np.array([sum(xs) / len(xs), sum(ys) / len(ys), 0.0])


def build_background() -> Mobject:
    bg = Rectangle(width=14.3, height=8.1, fill_color=PALETTE["background"],
                   fill_opacity=1, stroke_width=0)
    bg.set_z_index(-10)
    return bg


def title_card(text: str, subtitle: str = "") -> VGroup:
    parts = [Text(text, font_size=40, color=PALETTE["text"])]
    if subtitle:
        parts.append(Text(subtitle, font_size=26, color=PALETTE["muted"]))
    group = VGroup(*parts).arrange(DOWN, buff=0.2)
    group.set_z_index(5)
    return group


def caption(text: str) -> Text:
    t = Text(text, font_size=26, color=PALETTE["text"])
    t.set_z_index(5)
    return t


def label(text: str, color=None, size: int = 24) -> Text:
    t = Text(text, font_size=size, color=color or PALETTE["text"])
    t.set_z_index(5)
    return t


def emphasis_box(mobject, color=None) -> Rectangle:
    box = SurroundingRectangle(mobject, color=color or PALETTE["accent"], buff=0.15)
    box.set_fill(opacity=0)
    box.set_z_index(4)
    return box


class AssetLineup(Scene):
    def construct(self):
        self.add(build_background())
        title = title_card("Style Check", "diagram kit")
        title.move_to(grid_to_point("A2-A5"))
        self.add(title)
        circ = Circle(radius=0.6, color=PALETTE["primary"]).move_to(grid_to_point("C3-D3"))
        self.add(circ, emphasis_box(circ))
        self.add(label("a label", color=PALETTE["secondary"]).move_to(grid_to_point("C4-D4")))
        self.add(caption("caption text").move_to(grid_to_point("F2-F5")))
        self.wait(0.5)
"""
