"""Manim API knowledge base for repair-prompt grounding (De-Hallucinator style).

The dominant Manim codegen failure is API hallucination — nonexistent classes,
methods, or parameters. Instead of vector RAG (which TheoremExplainAgent's own
authors found inconsistent), this is prediction-driven exact lookup: regex the
API symbols out of the *failing* code region, match them against a signature
KB introspected from the installed manim, and inject only those signatures
into the repair prompt ("these are the ONLY valid signatures").

Build the KB once per environment:
    python -m manim_generator.api_kb          # writes manim_api_kb.json next to this file

At repair time, lookup() typically matches 3-10 symbols => <2 KB of prompt.
"""

import inspect
import json
import os
import re

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manim_api_kb.json")

_CLASS_CALL = re.compile(r"\b([A-Z][A-Za-z0-9_]+)\s*\(")
_METHOD_CALL = re.compile(r"\.([a-z_][a-z0-9_]*)\s*\(")

_kb_cache = None


def _first_doc_line(obj) -> str:
    doc = inspect.getdoc(obj)
    return doc.splitlines()[0].strip() if doc else ""


def _safe_signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "(...)"


def build_kb() -> dict:
    """Introspect the installed manim (+ manim_voiceover) into a signature KB."""
    import manim

    kb = {"classes": {}, "functions": {}}

    def index_class(name: str, cls: type):
        methods = {}
        for m_name, member in inspect.getmembers(cls):
            if m_name.startswith("_") or not callable(member):
                continue
            try:
                methods[m_name] = _safe_signature(member)
            except Exception:
                continue
        kb["classes"][name] = {
            "sig": name + _safe_signature(cls.__init__).replace("(self, ", "(").replace("(self)", "()"),
            "doc": _first_doc_line(cls),
            "methods": methods,
        }

    for name in dir(manim):
        if name.startswith("_"):
            continue
        obj = getattr(manim, name)
        if inspect.isclass(obj):
            index_class(name, obj)
        elif inspect.isfunction(obj):
            kb["functions"][name] = {
                "sig": name + _safe_signature(obj),
                "doc": _first_doc_line(obj),
            }

    try:
        from manim_voiceover import VoiceoverScene
        index_class("VoiceoverScene", VoiceoverScene)
    except ImportError:
        pass

    return kb


def load_kb() -> dict:
    global _kb_cache
    if _kb_cache is None:
        if os.path.exists(KB_PATH):
            with open(KB_PATH, "r", encoding="utf-8") as f:
                _kb_cache = json.load(f)
        else:
            _kb_cache = build_kb()
    return _kb_cache


def lookup(code_region: str, max_entries: int = 12) -> str:
    """Format an API-reference block for the symbols used in `code_region`.
    Returns "" when nothing matches (the repair prompt has a fallback line)."""
    kb = load_kb()
    lines: list[str] = []

    class_names = []
    for match in _CLASS_CALL.finditer(code_region):
        name = match.group(1)
        if name in kb["classes"] and name not in class_names:
            class_names.append(name)
    for name in class_names[:max_entries]:
        entry = kb["classes"][name]
        doc = f" — {entry['doc']}" if entry["doc"] else ""
        lines.append(f"class {entry['sig']}{doc}")

    for match in _CLASS_CALL.finditer(code_region):
        name = match.group(1)
        if name in kb["functions"]:
            entry = kb["functions"][name]
            line = f"def {entry['sig']}" + (f" — {entry['doc']}" if entry["doc"] else "")
            if line not in lines:
                lines.append(line)

    method_names = {m.group(1) for m in _METHOD_CALL.finditer(code_region)}
    # Prefer methods on classes actually instantiated in the region; fall back
    # to the Mobject family, where almost all mobject methods live.
    owners = class_names or [c for c in ("Mobject", "VMobject", "VGroup", "Scene") if c in kb["classes"]]
    for m_name in sorted(method_names):
        for owner in owners:
            methods = kb["classes"].get(owner, {}).get("methods", {})
            if m_name in methods:
                lines.append(f"{owner}.{m_name}{methods[m_name]}")
                break
        if len(lines) >= max_entries * 2:
            break

    # Flag Capitalized call targets that are NOT in the KB — the dominant
    # failure is a hallucinated animation/mobject (e.g. `Wiggle`) that no repair
    # can import because it does not exist. Naming it as unknown is the signal.
    known = set(kb["classes"]) | set(kb["functions"])
    unknown = []
    for match in _CLASS_CALL.finditer(code_region):
        name = match.group(1)
        if name not in known and name not in unknown and name.lower() != name:
            unknown.append(name)
    if unknown:
        lines.append(
            "UNKNOWN — these names are NOT part of Manim v0.18 or the asset kit; "
            "they do not exist and cannot be imported. Replace each with a real "
            f"construct: {', '.join(unknown[:max_entries])}"
        )

    return "\n".join(lines[: max_entries * 2 + 1])


if __name__ == "__main__":
    kb = build_kb()
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f)
    size_kb = os.path.getsize(KB_PATH) // 1024
    print(f"Wrote {KB_PATH} ({size_kb} KB): "
          f"{len(kb['classes'])} classes, {len(kb['functions'])} functions")
