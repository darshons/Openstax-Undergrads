"""LLM code generation, repair, and visual critique for scenario scenes.

Ported from the TheoremExplainAgent OpenStax fork (src/core/code_generator.py)
with the RAG/ChromaDB/Langfuse/context-learning paths removed. The
code-extraction fallback chain is kept verbatim — it is the product of many
observed LLM formatting failure modes (nested fences, <CODE> tags, bare-code
responses) and each branch earns its keep.
"""

import os
import re

from PIL import Image

from .gemini_client import GeminiClient

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

CODE_PATTERN = r"```python(.*)```"

EXTRACT_RETRY_PROMPT = """\
Please extract the Python code in the correct format using the pattern: {pattern}.
You MUST NOT include any other text or comments.
You MUST return the exact same code as in the previous response, NO CONTENT EDITING is allowed.
Previous response:
{response_text}
"""


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, f"{name}.txt"), "r", encoding="utf-8") as f:
        return f.read()


def fill_prompt(template: str, **kwargs: str) -> str:
    """Replace {key} placeholders without str.format(), which chokes on the
    literal braces that code snippets and JSON embedded in prompts contain."""
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template


class CodeGenerator:
    def __init__(self, client: GeminiClient):
        self.client = client

    # ---------------- generation ----------------

    def generate_scene_code(self, prompt: str, label: str = "code_generation") -> tuple[str, str]:
        """Run a filled code-generation prompt; return (code, raw_response)."""
        response_text = self.client.generate(prompt, label=label)
        code = self._extract_code_with_retries(response_text, CODE_PATTERN, label=label)
        return code, response_text

    # ---------------- repair ----------------

    def fix_code_errors(self, scene_plan: str, code: str, error: str,
                        api_docs: str = "") -> tuple[str, str]:
        """Full-file repair from a (truncated) render error. `api_docs` is the
        De-Hallucinator signature block injected when the knowledge base
        matched symbols in the failing code (may be empty)."""
        prompt = fill_prompt(
            load_prompt("prompt_fix_error_full"),
            scene_plan=scene_plan,
            code=code,
            error=error,
            api_docs=api_docs or "(no API reference matched — rely on core Manim v0.18 knowledge)",
        )
        response_text = self.client.generate(prompt, label="fix_error_full")
        fixed = self._extract_code_with_retries(response_text, CODE_PATTERN, label="fix_error_full")
        return fixed, response_text

    # ---------------- visual critique ----------------

    def visual_self_reflection_grid(self, code: str, grid_image: Image.Image,
                                    occupancy_table: str = "") -> tuple[str, str]:
        """Grid-anchored layout critic (Code2Video-style). `grid_image` is the
        snapshot with the labeled 6x6 grid already overlaid. Returns
        ("<LGTM>", response) when the layout is clean, else (fixed_code, response).
        """
        prompt = fill_prompt(
            load_prompt("prompt_visual_self_reflection_grid"),
            code=code,
            occupancy_table=occupancy_table or "(no occupancy table declared for this scene)",
        )
        response_text = self.client.generate(prompt, image=grid_image, label="grid_critic")
        if "<LGTM>" in response_text:
            return "<LGTM>", response_text
        fixed = self._extract_code_with_retries(response_text, CODE_PATTERN, label="grid_critic")
        return fixed, response_text

    def critique_asset_lineup(self, code: str, grid_image: Image.Image,
                             character_block: str) -> tuple[str, str]:
        """Critique the asset-kit lineup frame against the character
        descriptions. Returns ("<LGTM>", response) or (fixed_assets, response)."""
        prompt = fill_prompt(
            load_prompt("prompt_asset_lineup_critique"),
            code=code,
            character_block=character_block,
        )
        response_text = self.client.generate(prompt, image=grid_image, label="lineup_critique")
        if "<LGTM>" in response_text:
            return "<LGTM>", response_text
        fixed = self._extract_code_with_retries(response_text, CODE_PATTERN, label="lineup_critique")
        return fixed, response_text

    # ---------------- extraction ----------------

    def _extract_code_with_retries(self, response_text: str, pattern: str,
                                   label: str = "", max_retries: int = 5) -> str:
        for attempt in range(max_retries):
            code_match = re.search(pattern, response_text, re.DOTALL)
            if code_match:
                return code_match.group(1)

            # Fallback 1: structured tags (<FULL_CORRECTED_CODE> for fixes,
            # <CODE> for generation) — isolates code from <THINKING> prose,
            # then strips an inner ```python fence if present.
            for tag in ("FULL_CORRECTED_CODE", "CODE"):
                tag_match = re.search(rf"<{tag}>(.*?)</{tag}>", response_text, re.DOTALL)
                if tag_match:
                    inner = tag_match.group(1)
                    inner_fence = re.search(r"```(?:python)?\s*\n?(.*?)```", inner, re.DOTALL)
                    code = inner_fence.group(1) if inner_fence else inner
                    if "from manim import" in code or ("class" in code and "Scene" in code):
                        return code

            # Fallback 2: a fenced block with no/other language tag. Prefer the
            # LAST fenced block — earlier ones may sit inside <THINKING> prose.
            fenced = re.findall(r"```[a-zA-Z]*\s*\n?(.*?)```", response_text, re.DOTALL)
            for block in reversed(fenced):
                if "from manim import" in block or ("class" in block and "Scene" in block):
                    return block

            # Fallback 3: the WHOLE response is raw code (no prose, no fences).
            stripped = response_text.lstrip()
            if (
                "```" not in response_text
                and "<THINKING>" not in response_text
                and "from manim import" in response_text
                and stripped.startswith(("from ", "import ", "#", '"""'))
            ):
                return response_text

            if attempt < max_retries - 1:
                print(f"[{label}] attempt {attempt + 1}: no code pattern found, asking model to reformat")
                response_text = self.client.generate(
                    fill_prompt(EXTRACT_RETRY_PROMPT, pattern=pattern, response_text=response_text),
                    label=f"{label}_format_retry",
                )

        raise ValueError(f"[{label}] failed to extract code after {max_retries} attempts")
