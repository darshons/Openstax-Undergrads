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
from .prompt_builder import build_asset_kit_prompt
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
    """Generate assets.py, prove it renders (AssetLineup), and return its path.
    Falls back to a parameterized generic kit if the LLM kit never renders."""
    os.makedirs(build_dir, exist_ok=True)
    prompt = build_asset_kit_prompt(spec)
    code, _ = codegen.generate_scene_code(prompt, label="asset_kit")

    assets_path = os.path.join(build_dir, "assets.py")
    media_dir = os.path.join(build_dir, "media")
    contract = "The asset-kit module contract from the generation prompt:\n" + prompt

    for attempt in range(ASSET_KIT_MAX_REPAIRS + 1):
        with open(assets_path, "w", encoding="utf-8") as f:
            f.write(code)
        ok, stderr = renderer.render(assets_path, media_dir, scene_name="AssetLineup")
        if ok:
            log(f"[asset_kit] lineup rendered on attempt {attempt + 1}")
            return assets_path
        error = truncate_error_log(stderr)
        log(f"[asset_kit] render failed (attempt {attempt + 1}): {error.splitlines()[-1] if error else 'unknown'}")
        if attempt == ASSET_KIT_MAX_REPAIRS:
            break
        code, _ = codegen.fix_code_errors(contract, code, error)

    log("[asset_kit] LLM kit never rendered — using the parameterized fallback kit")
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


def extract_asset_api(assets_path: str) -> str:
    """Public API summary of the frozen assets.py, injected into the scene-plan
    and code-generation prompts."""
    with open(assets_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    lines = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            args = ", ".join(
                a.arg for a in node.args.args
            )
            lines.append(f"- {node.name}({args})")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("PALETTE", "VOICE_MAP"):
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
# Fallback kit: generic but functional avatars parameterized per character, so
# a broken LLM generation can never hard-block the whole scenario.
# ---------------------------------------------------------------------------

_FALLBACK_COLORS = ["#4E9AF1", "#F1A54E", "#7BC67B", "#C67BC6", "#F1D24E", "#6BD5C8"]


def build_fallback_kit(spec: ScenarioSpec) -> str:
    palette_chars = ",\n".join(
        f'    "{c.character_id}": "{_FALLBACK_COLORS[i % len(_FALLBACK_COLORS)]}"'
        for i, c in enumerate(spec.characters)
    )
    voice_map = ",\n".join(
        f'    "{c.character_id}": "{c.voice}"' for c in spec.characters
    )
    builders = "\n\n".join(
        f'''def build_{c.character_id}(scale: float = 1.0) -> VGroup:
    return _generic_avatar(PALETTE["{c.character_id}"], "{(c.name or c.character_id)[:1].upper()}", scale)'''
        for c in spec.characters
    )
    lineup_builds = ", ".join(f"build_{c.character_id}()" for c in spec.characters)
    lineup_names = ", ".join(f'"{c.name or c.character_id}"' for c in spec.characters)

    return f'''from manim import *

PALETTE = {{
    "background": "{FALLBACK_BACKGROUND}",
    "bubble_fill": "#F5F1E8",
    "bubble_text": "#1A1A2E",
    "accent_correct": "#5FBF77",
    "accent_incorrect": "#E2703A",
{palette_chars}
}}

VOICE_MAP = {{
{voice_map}
}}


def _generic_avatar(color: str, initial: str, scale: float = 1.0) -> VGroup:
    head = Circle(radius=0.45, color=color, fill_color=color, fill_opacity=1).shift(UP * 1.05)
    body = RoundedRectangle(corner_radius=0.25, width=1.1, height=1.6,
                            color=color, fill_color=color, fill_opacity=0.85)
    badge = Text(initial, font_size=30, color=WHITE).move_to(head)
    avatar = VGroup(body, head, badge)
    avatar.scale(scale).move_to(ORIGIN)
    return avatar


{builders}


def build_setting() -> VGroup:
    bg = Rectangle(width=14.3, height=8.1, fill_color=PALETTE["background"],
                   fill_opacity=1, stroke_width=0)
    floor = Rectangle(width=14.3, height=2.2, fill_color="#1A3A5C",
                      fill_opacity=1, stroke_width=0).align_to(bg, DOWN)
    setting = VGroup(bg, floor)
    setting.set_z_index(-10)
    return setting


def _wrap_text(text: str, max_chars: int = 38) -> str:
    words, lines, current = text.split(), [], ""
    for w in words:
        if len(current) + len(w) + 1 > max_chars:
            lines.append(current)
            current = w
        else:
            current = (current + " " + w).strip()
    lines.append(current)
    return "\\n".join(lines)


def make_speech_bubble(text: str, speaker: Mobject, direction=UP, max_width: float = 5.0) -> VGroup:
    label = Text(_wrap_text(text), font_size=24, color=PALETTE["bubble_text"], line_spacing=0.8)
    if label.width > max_width - 0.5:
        label.scale_to_fit_width(max_width - 0.5)
    box = RoundedRectangle(corner_radius=0.2, width=label.width + 0.5,
                           height=label.height + 0.4,
                           fill_color=PALETTE["bubble_fill"], fill_opacity=1,
                           stroke_color=PALETTE["bubble_text"], stroke_width=1.5)
    label.move_to(box)
    bubble = VGroup(box, label)
    bubble.next_to(speaker, direction, buff=0.3)
    # clamp inside the safe frame
    bubble.shift(RIGHT * max(0, -6.6 - bubble.get_left()[0]))
    bubble.shift(LEFT * max(0, bubble.get_right()[0] - 6.6))
    bubble.shift(UP * max(0, -3.5 - bubble.get_bottom()[1]))
    bubble.shift(DOWN * max(0, bubble.get_top()[1] - 3.5))
    tail = Triangle(fill_color=PALETTE["bubble_fill"], fill_opacity=1, stroke_width=0)
    tail.scale(0.15).rotate(PI).next_to(box, DOWN, buff=-0.05)
    bubble.add(tail)
    bubble.set_z_index(10)
    return bubble


def make_lower_third(name: str, role: str) -> VGroup:
    text = VGroup(
        Text(name, font_size=26, color=WHITE, weight=BOLD),
        Text(role, font_size=18, color="#CCCCCC"),
    ).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
    box = RoundedRectangle(corner_radius=0.12, width=text.width + 0.5,
                           height=text.height + 0.3,
                           fill_color="#1A1A2E", fill_opacity=0.85, stroke_width=0)
    text.move_to(box)
    banner = VGroup(box, text).to_corner(DL, buff=0.4)
    banner.set_z_index(10)
    return banner


class AssetLineup(Scene):
    def construct(self):
        self.add(build_setting())
        avatars = VGroup({lineup_builds}).arrange(RIGHT, buff=1.2)
        if avatars.width > 12:
            avatars.scale_to_fit_width(12)
        avatars.move_to(ORIGIN)
        self.add(avatars)
        names = [{lineup_names}]
        for avatar, name in zip(avatars, names):
            label = Text(name, font_size=22, color=WHITE).next_to(avatar, DOWN, buff=0.3)
            self.add(label)
        self.add(make_speech_bubble("Hello!", avatars[0]))
        self.wait(0.5)
'''
