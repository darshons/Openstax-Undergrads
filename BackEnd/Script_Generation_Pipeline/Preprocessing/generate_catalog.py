"""
Generate frontend/src/data/catalog.ts from the live OpenStax API.

Fetches the ABL (Approved Book List) and every book's Table of Contents,
then writes a complete catalog with all books, chapters, and sections.

Usage
-----
    python generate_catalog.py                  # write catalog.ts
    python generate_catalog.py --dry-run        # print to stdout only
    python generate_catalog.py --output out.ts  # custom output path
    python generate_catalog.py --workers 30     # parallel fetch concurrency
"""

import argparse
import html as html_mod
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants (mirrored from html_crawler.py)
# ---------------------------------------------------------------------------

ABL_URL = "https://corgi.ce.openstax.org/api/abl/"
TOC_URL_TEMPLATE = (
    "https://openstax-web-hosting-content-primary.s3.amazonaws.com"
    "/apps/archive/20260407.195030/contents/{book_uuid}@{commit_sha}.json"
)

INCLUDE_TARGET_TYPES = {"intro", "numbered-section"}

PALETTE = [
    "#d35400", "#c0392b", "#8e44ad", "#1a5276", "#9ccb3b",
    "#e74c3c", "#27ae60", "#52be80", "#f36f21", "#002569",
    "#1a4dbf", "#1565c0", "#16a085", "#2c3e50", "#f4c61f",
    "#e67e22", "#7f8c8d", "#5e6a71", "#2ecc71", "#3498db",
]

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "frontend" / "src" / "data" / "catalog.ts"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def strip_html(text: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def clean_title(raw: str) -> str:
    text = strip_html(raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chapter_name(raw: str) -> str:
    text = clean_title(raw)
    text = re.sub(r"^(Chapter|Unit)\s+\d+\s*", "", text).strip()
    return text


def number_from_slug(slug: str) -> str | None:
    m = re.match(r"^(\d+)-", slug)
    return m.group(1) if m else None


def section_number_from_slug(slug: str) -> str | None:
    m = re.match(r"^(\d+)-(\d+)-", slug)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    return None


def is_english(slug: str) -> bool:
    return all(ord(c) < 128 for c in slug)


def toc_has_units(toc: dict) -> bool:
    contents = toc.get("tree", {}).get("contents", [])
    return any(n.get("toc_type") == "unit" for n in contents)


def js_string(s: str) -> str:
    """Escape a string for use inside JS single quotes."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


# ---------------------------------------------------------------------------
# API fetching
# ---------------------------------------------------------------------------


def fetch_abl() -> list[dict]:
    print(f"Fetching ABL from {ABL_URL} ...")
    resp = requests.get(ABL_URL, timeout=30)
    resp.raise_for_status()
    books = resp.json()
    print(f"  {len(books)} books in ABL")
    return books


def fetch_toc(book: dict, retries: int = 3) -> dict | None:
    import time
    uuid = book.get("uuid", "")
    sha = book.get("commit_sha", "")[:7]
    url = TOC_URL_TEMPLATE.format(book_uuid=uuid, commit_sha=sha)
    for attempt in range(1 + retries):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt < retries:
                time.sleep(1 + attempt)
            else:
                print(f"  WARN: failed to fetch ToC for {book.get('slug')} after {1 + retries} attempts")
                return None


def fetch_all_tocs(
    books: list[dict], max_workers: int = 5
) -> dict[str, dict]:
    import time
    results: dict[str, dict] = {}
    for i, book in enumerate(books, 1):
        slug = book["slug"]
        toc = fetch_toc(book)
        if toc:
            results[slug] = toc
        if i % 20 == 0:
            print(f"    {i}/{len(books)} ...")
        time.sleep(0.15)
    print(f"  Fetched {len(results)}/{len(books)} ToCs successfully")
    return results


# ---------------------------------------------------------------------------
# ToC parsing
# ---------------------------------------------------------------------------


def parse_sections(chapter_node: dict) -> list[dict]:
    secs = []
    for child in chapter_node.get("contents", []):
        if child.get("toc_type") != "book-content":
            continue
        if child.get("toc_target_type", "") not in INCLUDE_TARGET_TYPES:
            continue
        slug = child.get("slug", "")
        sec_n = section_number_from_slug(slug)
        if not sec_n:
            continue
        title = clean_title(child.get("title", ""))
        title = re.sub(r"^\d+\.\d+\s*", "", title).strip()
        if title:
            secs.append({"n": sec_n, "t": title})
    return secs


def parse_chapters_from_parent(parent_node: dict, unit_num: int | None = None) -> list[dict]:
    chapters = []
    for child in parent_node.get("contents", []):
        if child.get("toc_type") != "chapter":
            continue
        slug = child.get("slug", "")
        num = number_from_slug(slug)
        if not num:
            continue
        name = chapter_name(child.get("title", ""))
        secs = parse_sections(child)
        ch: dict = {"n": num.zfill(2), "name": name, "secs": secs}
        if unit_num is not None:
            ch["unit"] = unit_num
        chapters.append(ch)
    return chapters


def parse_book(toc: dict) -> list[dict]:
    tree = toc.get("tree", toc)
    if toc_has_units(toc):
        chapters = []
        for node in tree.get("contents", []):
            if node.get("toc_type") != "unit":
                continue
            unit_n = number_from_slug(node.get("slug", ""))
            u_num = int(unit_n) if unit_n else None
            chapters.extend(parse_chapters_from_parent(node, unit_num=u_num))
        return chapters
    else:
        return parse_chapters_from_parent(tree)


# ---------------------------------------------------------------------------
# TypeScript generation
# ---------------------------------------------------------------------------

TS_HEADER = """\
import type { GenerateRequest, ModelChoice, VideoType } from '../types/script';

// ── Catalog types (auto-generated by generate_catalog.py) ─────────────────

export interface CatalogSection {
  n: string;
  t: string;
}

export interface CatalogChapter {
  n: string;
  unit?: number;
  name: string;
  secs: CatalogSection[];
}

export interface CatalogBook {
  id: string;
  title: string;
  sub: string;
  color: string;
  bookTitle: string;
  chapters: CatalogChapter[];
}

// ── Full OpenStax catalog ─────────────────────────────────────────────────

export const CATALOG: CatalogBook[] = [
"""

TS_FOOTER = """\
];

// ── Utility functions ──────────────────────────────────────────────────────

interface LookupResult {
  book: CatalogBook;
  chap: CatalogChapter;
  secN: string;
}

export function lookupSection(id: string): LookupResult | null {
  const [bookId, chapN, secN] = id.split(':');
  const book = CATALOG.find(b => b.id === bookId);
  if (!book) return null;
  const chap = book.chapters.find(c => c.n === chapN);
  if (!chap) return null;
  return { book, chap, secN };
}

interface BuildRequestParams {
  selected: Set<string>;
  model: ModelChoice;
  videoType: VideoType;
  userQuery: string;
}

export function buildGenerateRequest({
  selected,
  model,
  videoType,
  userQuery,
}: BuildRequestParams): GenerateRequest | null {
  const firstId = Array.from(selected)[0];
  const hit = firstId ? lookupSection(firstId) : null;
  if (!hit) return null;
  return {
    book_title: hit.book.bookTitle,
    unit_num: hit.chap.unit ?? null,
    chapter_num: parseInt(hit.chap.n, 10),
    page_num: hit.secN,
    user_query: userQuery,
    model_choice: model,
    video_type: videoType,
  };
}
"""


def format_section(sec: dict) -> str:
    return f"{{ n: '{js_string(sec['n'])}', t: '{js_string(sec['t'])}' }}"


def format_chapter(ch: dict) -> str:
    secs_str = ", ".join(format_section(s) for s in ch["secs"])
    unit_part = f" unit: {ch['unit']}," if "unit" in ch else ""
    return (
        f"      {{ n: '{ch['n']}',{unit_part}"
        f" name: '{js_string(ch['name'])}', secs: [{secs_str}] }}"
    )


def format_book(book: dict) -> str:
    lines = [
        "  {",
        f"    id: '{js_string(book['id'])}', title: '{js_string(book['title'])}',",
        f"    sub: '{js_string(book['sub'])}', color: '{book['color']}',",
        f"    bookTitle: '{js_string(book['bookTitle'])}',",
        "    chapters: [",
    ]
    for ch in book["chapters"]:
        lines.append(format_chapter(ch) + ",")
    lines.append("    ],")
    lines.append("  }")
    return "\n".join(lines)


def generate_ts(books: list[dict]) -> str:
    body = ",\n".join(format_book(b) for b in books)
    return TS_HEADER + body + "\n" + TS_FOOTER


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_catalog(max_workers: int = 20) -> list[dict]:
    abl = fetch_abl()
    english = [b for b in abl if is_english(b.get("slug", ""))]
    print(f"  {len(english)} English books (filtered {len(abl) - len(english)} non-English)")

    print(f"Fetching ToCs with {max_workers} workers ...")
    tocs = fetch_all_tocs(english, max_workers=max_workers)

    catalog: list[dict] = []
    skipped = 0
    for i, book in enumerate(english):
        slug = book.get("slug", "")
        if slug not in tocs:
            continue
        toc = tocs[slug]
        chapters = parse_book(toc)
        if not chapters:
            skipped += 1
            continue

        book_title = clean_title(toc.get("tree", {}).get("title", slug))
        catalog.append({
            "id": slug,
            "title": book_title,
            "sub": "",
            "color": PALETTE[i % len(PALETTE)],
            "bookTitle": slug,
            "chapters": chapters,
        })

    catalog.sort(key=lambda b: b["title"].lower())
    total_chapters = sum(len(b["chapters"]) for b in catalog)
    total_sections = sum(len(c["secs"]) for b in catalog for c in b["chapters"])
    print(f"\nCatalog: {len(catalog)} books, {total_chapters} chapters, {total_sections} sections")
    if skipped:
        print(f"  Skipped {skipped} books with no parseable chapters")
    return catalog


def main():
    ap = argparse.ArgumentParser(description="Generate catalog.ts from OpenStax API")
    ap.add_argument("--workers", type=int, default=5, help="Parallel fetch workers (default 5)")
    ap.add_argument("--output", type=str, default=None, help="Output path (default: frontend/src/data/catalog.ts)")
    ap.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing file")
    args = ap.parse_args()

    catalog = build_catalog(max_workers=args.workers)
    ts_content = generate_ts(catalog)

    if args.dry_run:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(ts_content)
        return

    out_path = Path(args.output) if args.output else DEFAULT_OUTPUT
    out_path.write_text(ts_content, encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"  {len(ts_content):,} bytes")


if __name__ == "__main__":
    main()
