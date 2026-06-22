#!/usr/bin/env python3
"""
OpenStax -> TheoremExplainAgent adapter.

Converts an OpenStax book (CNXML modules + a collection XML, the format published
in the openstax/osbooks-* GitHub repositories) into the JSON list of
{theorem, description, ...} items that ``generate_video.py`` consumes via
``--theorems_path``.

Each OpenStax *section* (a module) becomes one "topic" for the video pipeline:
  - "theorem"  <- the section title
  - "description" <- learning objectives + the opening body paragraphs, cleaned
                     of markup, so the planner model has rich context.

Typical usage
-------------
1. Download a book bundle (shallow clone is enough)::

     git clone --depth 1 https://github.com/openstax/osbooks-college-physics-bundle.git

2. Convert a whole book to topic JSON::

     python openstax_adapter.py \
         --book-dir osbooks-college-physics-bundle \
         --collection college-physics-2e \
         --out data/openstax/college_physics.json

3. Or convert just one chapter (case-insensitive substring match on the chapter
   title) and cap the number of sections::

     python openstax_adapter.py \
         --book-dir osbooks-college-physics-bundle \
         --collection college-physics-2e \
         --chapter "Kinematics" \
         --max-sections 5 \
         --out data/openstax/kinematics.json

The resulting JSON plugs straight into the generator::

     python generate_video.py \
         --model gemini/gemini-2.0-flash-001 \
         --helper_model gemini/gemini-2.0-flash-001 \
         --theorems_path data/openstax/kinematics.json \
         --output_dir output/openstax_kinematics
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# CNXML / collection XML namespaces.
NS = {
    "col": "http://cnx.rice.edu/collxml",
    "md": "http://cnx.rice.edu/mdml",
    "c": "http://cnx.rice.edu/cnxml",
    "m": "http://www.w3.org/1998/Math/MathML",
}


# --------------------------------------------------------------------------- #
# Text extraction helpers
# --------------------------------------------------------------------------- #
def _local(tag):
    """Strip the {namespace} prefix from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _text_of(elem):
    """
    Recursively collect human-readable text from a CNXML element.

    MathML subtrees are reduced to their textual content (good enough as context
    for the LLM). Whitespace is normalized.
    """
    parts = []

    def walk(node):
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(elem)
    text = " ".join(parts)
    # Collapse whitespace and tidy spacing around punctuation.
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def _find_sections(content, cls):
    """Yield <section> elements whose class attribute matches cls."""
    for sec in content.iter():
        if _local(sec.tag) == "section" and sec.get("class") == cls:
            yield sec


def _learning_objectives(content):
    """Return the learning-objectives list items as a list of strings."""
    objectives = []
    for sec in _find_sections(content, "learning-objectives"):
        for item in sec.iter():
            if _local(item.tag) == "item":
                txt = _text_of(item)
                if txt:
                    objectives.append(txt)
    return objectives


def _body_paragraphs(content, max_chars):
    """
    Collect the opening body <para> text, skipping figure captions and the
    learning-objectives block, up to roughly max_chars characters.
    """
    # Tags whose text is not useful narrative context.
    skip_inside = {"figure", "caption", "media", "list"}
    out = []
    total = 0
    for para in content.iter():
        if _local(para.tag) != "para":
            continue
        # Skip paragraphs that are really just figure wrappers.
        if any(_local(c.tag) in skip_inside for c in para):
            # Only skip if the para has essentially no direct prose.
            direct = (para.text or "").strip()
            if not direct:
                continue
        txt = _text_of(para)
        if len(txt) < 40:  # skip stubs / captions
            continue
        # Skip the boilerplate lead-in to learning objectives.
        if txt.lower().startswith("by the end of this section"):
            continue
        out.append(txt)
        total += len(txt)
        if total >= max_chars:
            break
    return out


def build_description(content, max_chars=1200):
    """Build a rich description string from a module's content element."""
    pieces = []
    objectives = _learning_objectives(content)
    if objectives:
        pieces.append("Learning objectives: " + "; ".join(objectives) + ".")

    remaining = max(200, max_chars - sum(len(p) for p in pieces))
    paras = _body_paragraphs(content, remaining)
    if paras:
        pieces.append(" ".join(paras))

    desc = " ".join(pieces).strip()
    if len(desc) > max_chars:
        desc = desc[:max_chars].rsplit(" ", 1)[0] + "…"
    return desc


# --------------------------------------------------------------------------- #
# Module / collection parsing
# --------------------------------------------------------------------------- #
def module_path(book_dir, module_id):
    """Locate a module's index.cnxml inside an osbooks bundle."""
    candidate = os.path.join(book_dir, "modules", module_id, "index.cnxml")
    if os.path.exists(candidate):
        return candidate
    # Some bundles place the cnxml directly (rare); fall back to a search.
    for root, _dirs, files in os.walk(os.path.join(book_dir, "modules")):
        if os.path.basename(root) == module_id and "index.cnxml" in files:
            return os.path.join(root, "index.cnxml")
    return None


def parse_module(book_dir, module_id, max_desc_chars):
    """Parse one module into a topic dict, or None if it can't be read."""
    path = module_path(book_dir, module_id)
    if not path:
        sys.stderr.write(f"  ! module {module_id}: index.cnxml not found, skipping\n")
        return None
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        sys.stderr.write(f"  ! module {module_id}: XML parse error ({exc}), skipping\n")
        return None
    root = tree.getroot()

    # Title: prefer <document><title>, fall back to md:title.
    title = None
    for child in root:
        if _local(child.tag) == "title":
            title = _text_of(child)
            break
    if not title:
        md_title = root.find(".//md:title", NS)
        title = _text_of(md_title) if md_title is not None else module_id

    content = root.find(".//c:content", NS)
    if content is None:
        # Namespace-agnostic fallback.
        content = next((e for e in root.iter() if _local(e.tag) == "content"), None)
    description = build_description(content, max_desc_chars) if content is not None else ""

    return {
        "theorem": title,
        "description": description or title,
        "difficulty": "",
        "remark": "",
        "subfield": "",
        "source": "openstax",
        "module_id": module_id,
    }


def iter_collection(collection_path):
    """
    Walk a collection XML, yielding (chapter_title, module_id) in book order.

    Modules that sit directly under the root (not inside a subcollection) get a
    chapter title of "" (e.g. the book preface).
    """
    tree = ET.parse(collection_path)
    root = tree.getroot()
    content = root.find("col:content", NS)
    if content is None:
        content = next((e for e in root.iter() if _local(e.tag) == "content"), None)

    def walk(node, chapter_title):
        for child in node:
            tag = _local(child.tag)
            if tag == "subcollection":
                title_el = child.find("md:title", NS)
                sub_title = _text_of(title_el) if title_el is not None else chapter_title
                sub_content = child.find("col:content", NS)
                if sub_content is not None:
                    yield from walk(sub_content, sub_title)
            elif tag == "module":
                doc = child.get("document")
                if doc:
                    yield chapter_title, doc
            elif tag == "content":
                yield from walk(child, chapter_title)

    yield from walk(content, "")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def resolve_collection(book_dir, collection):
    """Resolve a --collection value to a collection XML path."""
    coll_dir = os.path.join(book_dir, "collections")
    # Exact filename, slug, or substring match.
    candidates = []
    if os.path.isdir(coll_dir):
        candidates = sorted(
            f for f in os.listdir(coll_dir) if f.endswith(".collection.xml")
        )
    if not collection:
        if len(candidates) == 1:
            return os.path.join(coll_dir, candidates[0])
        raise SystemExit(
            "Multiple collections found; pass --collection. Available: "
            + ", ".join(c.replace(".collection.xml", "") for c in candidates)
        )
    # Allow passing a direct path.
    if os.path.exists(collection):
        return collection
    for f in candidates:
        if collection in f:
            return os.path.join(coll_dir, f)
    raise SystemExit(
        f"Collection '{collection}' not found. Available: "
        + ", ".join(c.replace(".collection.xml", "") for c in candidates)
    )


def main():
    ap = argparse.ArgumentParser(
        description="Convert an OpenStax CNXML book into TheoremExplainAgent topic JSON."
    )
    ap.add_argument(
        "--book-dir",
        required=True,
        help="Path to an openstax/osbooks-* bundle checkout (contains modules/ and collections/).",
    )
    ap.add_argument(
        "--collection",
        default=None,
        help="Collection slug/filename/path (e.g. 'college-physics-2e'). "
        "Optional if the book has exactly one collection.",
    )
    ap.add_argument(
        "--chapter",
        default=None,
        help="Only include sections from chapters whose title contains this string "
        "(case-insensitive).",
    )
    ap.add_argument(
        "--max-sections",
        type=int,
        default=None,
        help="Cap the number of sections (topics) emitted.",
    )
    ap.add_argument(
        "--max-desc-chars",
        type=int,
        default=1200,
        help="Maximum length of each generated description (default 1200).",
    )
    ap.add_argument(
        "--skip-intro",
        action="store_true",
        help="Skip sections whose title starts with 'Introduction'.",
    )
    ap.add_argument("--out", required=True, help="Output JSON path.")
    args = ap.parse_args()

    collection_path = resolve_collection(args.book_dir, args.collection)
    sys.stderr.write(f"Using collection: {collection_path}\n")

    chapter_filter = args.chapter.lower() if args.chapter else None
    topics = []
    seen = set()
    for chapter_title, module_id in iter_collection(collection_path):
        if chapter_filter and chapter_filter not in chapter_title.lower():
            continue
        if module_id in seen:
            continue
        seen.add(module_id)

        topic = parse_module(args.book_dir, module_id, args.max_desc_chars)
        if topic is None:
            continue
        if args.skip_intro and topic["theorem"].lower().startswith("introduction"):
            continue
        topic["chapter"] = chapter_title
        topics.append(topic)
        sys.stderr.write(f"  + {chapter_title or '(root)'} :: {topic['theorem']}\n")

        if args.max_sections and len(topics) >= args.max_sections:
            break

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)

    sys.stderr.write(f"\nWrote {len(topics)} topics -> {args.out}\n")


if __name__ == "__main__":
    main()
