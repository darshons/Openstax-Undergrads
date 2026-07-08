"""ScopeRefine hierarchical error repair (Code2Video, arXiv 2510.01174).

Instead of regenerating the whole scene on every render failure, escalate:
  1. LINE scope  — fix the ~7 lines around the traceback's failing line (<=2 tries)
  2. BLOCK scope — fix the enclosing beat/function block                (<=2 tries)
  3. FULL scope  — regenerate the whole file (last resort)
Code2Video reports removing this escalation nearly tripled generation time,
because whole-file regen is the slow, drift-prone path. Each attempt's prompt
carries the RITL-truncated error tail plus the De-Hallucinator API signatures
matched in the failing region.
"""

import ast
import re

from . import api_kb
from .code_generator import CodeGenerator, fill_prompt, load_prompt
from .video_renderer import VideoRenderer, extract_failing_line, truncate_error_log

LINE_CONTEXT = 3           # lines of context on each side of the failing line
LINE_ATTEMPTS = 2
BLOCK_ATTEMPTS = 2
# A surgical fix should not balloon the region. If the model returns a
# replacement far larger than what it replaced, it ignored the "only these
# lines" instruction (observed: a 6-line block "fixed" into 400+ lines of
# prose-as-code). Reject it and let the next scope / full regen handle it.
MAX_REPLACEMENT_GROWTH = 3.0

_FIXED_LINES = re.compile(r"<FIXED_LINES>\s*```python\n?(.*?)```", re.DOTALL)


def _replacement_is_sane(replacement: str, original_span: int) -> bool:
    new_lines = replacement.strip().count("\n") + 1
    return new_lines <= max(12, original_span * MAX_REPLACEMENT_GROWTH)


def _parses(source: str) -> bool:
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


def _region(lines: list[str], start: int, end: int, mark: bool) -> str:
    """1-indexed inclusive slice; optionally >>> mark the target lines."""
    out = []
    for i in range(max(1, start), min(len(lines), end) + 1):
        prefix = ">>> " if mark and start <= i <= end else "    "
        out.append(f"{prefix}{lines[i - 1]}")
    return "\n".join(out)


def _block_bounds(lines: list[str], failing_line: int) -> tuple[int, int]:
    """Enclosing block = from the nearest less-indented `with`/`def` header
    above the failing line, down to where indentation returns to that header's
    level."""
    idx = failing_line - 1
    if idx < 0 or idx >= len(lines):
        return failing_line, failing_line
    header = idx
    for j in range(idx, -1, -1):
        stripped = lines[j].lstrip()
        if stripped.startswith(("with ", "def ", "for ", "if ")):
            header = j
            break
    header_indent = len(lines[header]) - len(lines[header].lstrip())
    end = header
    for j in range(header + 1, len(lines)):
        if lines[j].strip() and (len(lines[j]) - len(lines[j].lstrip())) <= header_indent:
            break
        end = j
    return header + 1, end + 1  # back to 1-indexed inclusive


def _apply_replacement(lines: list[str], start: int, end: int, replacement: str) -> str:
    new_lines = replacement.rstrip("\n").split("\n")
    return "\n".join(lines[: start - 1] + new_lines + lines[end:]) + "\n"


def scope_refine_repair(
    scene_id: int,
    code: str,
    stderr: str,
    scene_plan: str,
    code_path: str,
    codegen: CodeGenerator,
    renderer: VideoRenderer,
    media_dir: str,
    scene_name: str,
    log=print,
) -> tuple[str, bool, str]:
    """Try line -> block -> full repair, re-rendering after each. Returns
    (code, success, last_stderr). The caller writes versioned files and owns
    the overall retry budget; this function makes the escalating attempts for
    ONE render failure."""
    lines = code.split("\n")
    failing_line = extract_failing_line(stderr, code_path)
    error = truncate_error_log(stderr, code_path)

    # ---- 1 & 2: line then block scope (only if we located a line) ----
    scopes = []
    if failing_line:
        s, e = max(1, failing_line - LINE_CONTEXT), failing_line + LINE_CONTEXT
        scopes.append(("prompt_fix_error_line", s, e, LINE_ATTEMPTS))
        bs, be = _block_bounds(lines, failing_line)
        scopes.append(("prompt_fix_error_block", bs, be, BLOCK_ATTEMPTS))

    for template_name, start, end, attempts in scopes:
        api_docs = api_kb.lookup("\n".join(lines[start - 1:end])) or \
            "(no API reference matched — rely on core Manim v0.18 knowledge)"
        for _ in range(attempts):
            prompt = fill_prompt(
                load_prompt(template_name),
                error=error,
                start_line=start,
                end_line=end,
                region=_region(lines, start - LINE_CONTEXT, end + LINE_CONTEXT, mark=True),
                api_docs=api_docs,
            )
            response = codegen.client.generate(prompt, label=f"repair_{template_name}_{scene_id}")
            match = _FIXED_LINES.search(response)
            if not match:
                continue
            scope = template_name.rsplit("_", 1)[-1]
            # Guard against a runaway "surgical" fix corrupting the file: reject
            # a replacement that balloons the region or breaks the parse, and
            # move on WITHOUT poisoning the working copy.
            if not _replacement_is_sane(match.group(1), end - start + 1):
                log(f"[repair] scene {scene_id} {scope}-scope fix rejected (too large), escalating")
                break
            candidate = _apply_replacement(lines, start, end, match.group(1))
            if not _parses(candidate):
                log(f"[repair] scene {scene_id} {scope}-scope fix rejected (won't parse), retrying")
                continue
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(candidate)
            ok, new_stderr = renderer.render(code_path, media_dir, scene_name=scene_name)
            if ok:
                log(f"[repair] scene {scene_id} fixed at {scope} scope")
                return candidate, True, ""
            # Accept the candidate as the new working copy only if it parses
            # (it does, checked above) AND it did not make things worse. Keep
            # the failing-line tracking pointed at the newest render.
            lines = candidate.split("\n")
            stderr = new_stderr
            error = truncate_error_log(new_stderr, code_path)
            failing_line = extract_failing_line(new_stderr, code_path) or failing_line

    # ---- 3: full-file regen (last resort) ----
    log(f"[repair] scene {scene_id} escalating to full-file regeneration")
    api_docs = api_kb.lookup(code)
    fixed, _ = codegen.fix_code_errors(scene_plan, "\n".join(lines), error, api_docs=api_docs)
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(fixed)
    ok, new_stderr = renderer.render(code_path, media_dir, scene_name=scene_name)
    return fixed, ok, new_stderr
