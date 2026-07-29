"""LLM client selection for the manim pipeline.

``make_client(model)`` returns the Gemini client when GEMINI_API_KEY is set,
otherwise a local fallback that shells each prompt to the Claude Code CLI
(``claude -p``) — the same pattern as
Script_Generation_Pipeline/Script_With_Dpoints/local_script_generation.py — so
the pipeline runs on machines that have Claude Code credentials (~/.claude)
but no API keys at all.

Both clients expose the same contract the pipeline codes against:
    client.generate(prompt: str, image: PIL.Image | None = None, label: str = "") -> str
"""

import os
import shutil
import subprocess
import tempfile
import time

# A single code-generation call can be large; keep a generous per-call cap so a
# stuck CLI invocation fails and retries instead of hanging the serial pipeline.
CLAUDE_CLI_TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_CLI_TIMEOUT_SECONDS", "900"))
CLAUDE_CLI_MODEL = os.environ.get("CLAUDE_CLI_MODEL", "sonnet")
MAX_ATTEMPTS = 3


def _find_claude_cli() -> str:
    """Locate the claude CLI on PATH or in the default install location."""
    found = shutil.which("claude")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError(
        "No GEMINI_API_KEY is set and the 'claude' CLI was not found on PATH "
        "or at ~/.local/bin/claude. Set GEMINI_API_KEY or install Claude Code."
    )


class ClaudeCliClient:
    """GeminiClient-compatible client backed by `claude -p`.

    Text prompts go in on stdin; the plain-text completion comes back on
    stdout. Vision calls (the grid critic / lineup critique pass a PIL image)
    are handled by writing the image to a temp PNG and letting the CLI read it
    with its Read tool (pre-allowed via --allowedTools, so print mode never
    blocks on a permission prompt).
    """

    def __init__(self, model: str | None = None):
        # Gemini model ids leak through pipeline defaults; map anything that
        # isn't a claude alias/id to the configured CLI model.
        if not model or not (model.startswith("claude") or model in ("sonnet", "opus", "haiku")):
            model = CLAUDE_CLI_MODEL
        self.model = model
        self._cli = _find_claude_cli()

    def generate(self, prompt: str, image=None, label: str = "") -> str:
        image_path = None
        try:
            if image is not None:
                fd, image_path = tempfile.mkstemp(prefix="manim_critic_", suffix=".png")
                os.close(fd)
                image.save(image_path)
                prompt = (
                    f"First, use the Read tool to view the image at {image_path} "
                    "— it is the rendered frame you must critique. Then follow "
                    "the instructions below.\n\n" + prompt
                )

            cmd = [self._cli, "-p", "--output-format", "text", "--model", self.model]
            if image_path is not None:
                cmd += ["--allowedTools", "Read"]

            delay = 5.0
            last_err: Exception | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    result = subprocess.run(
                        cmd,
                        input=prompt,
                        capture_output=True,
                        text=True,
                        timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout
                    last_err = RuntimeError(
                        f"claude CLI exit {result.returncode} "
                        f"({label or 'generate'}): {result.stderr.strip()[:500]}"
                    )
                except subprocess.TimeoutExpired as e:
                    last_err = e
                if attempt < MAX_ATTEMPTS:
                    print(f"[claude-cli:{label}] {last_err}; retry {attempt}/{MAX_ATTEMPTS} in {delay:.0f}s")
                    time.sleep(delay)
                    delay *= 2
            raise last_err
        finally:
            if image_path is not None:
                try:
                    os.remove(image_path)
                except OSError:
                    pass


def make_client(model: str):
    """GeminiClient when a key exists, ClaudeCliClient otherwise."""
    if os.environ.get("GEMINI_API_KEY"):
        from .gemini_client import GeminiClient

        return GeminiClient(model=model)
    print("[llm_client] GEMINI_API_KEY not set — using local Claude Code CLI fallback")
    return ClaudeCliClient(model=model)
