"""Local script generation provider.

Shells out to the Claude Code CLI (`claude -p`) instead of calling the
Anthropic API directly, so script generation works on machines that have
Claude Code credentials (~/.claude) but no ANTHROPIC_API_KEY.

The prompt is delivered on stdin; the response is plain text from which the
script JSON is extracted (markdown code fences are tolerated and stripped).
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from Script_Generation_Pipeline.prompt_assembly import build_system_prompt

logger = logging.getLogger(__name__)

# Script generation over a full textbook chapter can take several minutes.
CLAUDE_CLI_TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_CLI_TIMEOUT_SECONDS", "900"))
CLAUDE_CLI_MODEL = os.environ.get("CLAUDE_CLI_MODEL", "sonnet")


def _find_claude_cli() -> str:
    """Locate the claude CLI on PATH or in the default install location."""
    found = shutil.which("claude")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError(
        "The 'claude' CLI was not found on PATH or at ~/.local/bin/claude. "
        "Install Claude Code or set ANTHROPIC_API_KEY to use the 'anthropic' provider."
    )


def _extract_json(raw_text: str) -> dict:
    """Extract a JSON object from model output, stripping markdown fences."""
    text = raw_text.strip()

    # Prefer the contents of a fenced code block if one is present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError(
            f"No JSON object found in claude CLI output (first 500 chars): {raw_text[:500]!r}"
        )
    return json.loads(text[start:end])


def generate_script_with_decision_points_local(
    markdown_file_path, user_query
) -> tuple[dict | None, list[str | None]]:
    """Same contract as the anthropic/gemini providers: returns (script_json,
    file_ids). Nothing is uploaded anywhere, so file_ids is always empty."""

    system_prompt = build_system_prompt()

    project_dir = Path(__file__).resolve().parents[1]
    json_template = (
        project_dir / "_JSON_Templates" / "script_gen_with_dpoints.json"
    ).read_text(encoding="utf-8")

    textbook_content = Path(markdown_file_path).read_text(encoding="utf-8")

    prompt = (
        f"{system_prompt}\n\n"
        f"# Textbook Chapter\n\n{textbook_content}\n\n"
        f"# JSON Script Template\n\n```json\n{json_template}\n```\n\n"
        f"# User Request\n\n{user_query.strip()}\n\n"
        "Respond with ONLY the JSON object (no prose, no markdown fences)."
    )

    cli = _find_claude_cli()
    cmd = [cli, "-p", "--output-format", "text", "--model", CLAUDE_CLI_MODEL]
    logger.info("Running local script generation via claude CLI: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited with code {result.returncode}: "
            f"{result.stderr.strip()[:1000]}"
        )

    output_json = _extract_json(result.stdout)
    return output_json, []


def delete_uploaded_files_local(file_ids: list):
    """No-op: the local provider never uploads files anywhere."""
    return None
