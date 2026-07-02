"""
OpenStax Textbook Crawler
=========================
Search the textbook to extract the demanded textbook pages and turn it into a clean context for AI.
The List of Textbooks For book_title (ABL): https://corgi.ce.openstax.org/api/abl/
=========================
For each level (unit / chapter / page), provide either a number or an exact name.
Note: only provide one of them, not both.

unit_num   / unit_name    (required; provide exactly one)
chapter_num / chapter_name (optional; omit to crawl all chapters)
page_num   / page_name    (optional; omit to crawl all pages)

Examples:
crawl("University Physics Volume 1", unit_num=1)
crawl("University Physics Volume 1", unit_num=1, chapter_num=2)
crawl("University Physics Volume 1", unit_num=1, chapter_num=2, page_num="2.1")
crawl("University Physics Volume 1", unit_name="Optics", chapter_name="The Nature of Light")
=========================
Requirements:
pip install requests beautifulsoup4 lxml
pip install markdownify
=========================
Possible future changes:
1. Current crawler only takes care of "book-content" inside a chapter. In order to include content like book review
consider changing get_all_pages -> visit function. The recursion does not work right now.
2. We use open source library for dealing with xhtml pages in fetch_page_xhtml.
3.  _matches_by_name is not fully working right now, but we should remove it once we only allow user to input exact title name
or number.
4. to change how xhtml is parsed, change parse_page_xhtml().
"""

import os
import re
import json
import time
import requests
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from pathlib import Path

# =========================
# CONFIGURATION
# =========================

ABL_URL = os.environ.get("ABL_URL", "https://corgi.ce.openstax.org/api/abl/")
TOC_URL_TEMPLATE = os.environ.get(
    "TOC_URL_TEMPLATE",
    " https://openstax-web-hosting-content-primary.s3.amazonaws.com/apps/archive/20260407.195030/contents/{book_uuid}@{commit_sha}.json",
)
PAGE_URL_TEMPLATE = os.environ.get(
    "PAGE_URL_TEMPLATE",
    "https://openstax-web-hosting-content-primary.s3.amazonaws.com/apps/archive/20260407.195030/contents/{book_uuid}@{commit_sha}:{page_id}.xhtml",
)

REQUEST_DELAY = 0.3

INCLUDE_TARGET_TYPES = {"intro", "numbered-section"}


# =========================
# Regex matching unitilities functions [need to be changed later.]
# =========================


def strip_html(text: str) -> str:
    """Remove HTML tags from OpenStax title strings before any comparison."""
    return re.sub(r"<[^>]+>", " ", text).strip()


def normalize(s: str) -> str:
    """Lowercase and collapse all whitespace."""
    return " ".join(s.lower().split())


def build_url(template: str, values: dict) -> str:
    """Replace {placeholder} tokens in a URL template with real values."""
    url = template
    for key, val in values.items():
        url = url.replace(f"{{{key}}}", str(val))
    return url


# =========================
# strict matcher
# =========================


def _matches_by_number(node: dict, num: int | str) -> bool:
    """
    Match a unit or chapter node by its leading number.

    How it works
    ------------
    OpenStax slugs are always formatted as  "{number}-{rest-of-title}",
    e.g. "1-the-nature-of-light", "3-biological-macromolecules".
    We simply check whether the slug starts with  "{num}-".

    Examples
        num=1   slug "1-the-nature-of-light"           → True
        num=1   slug "11-quantum-mechanics"             → False  (starts with "11-", not "1-")
        num=3   slug "3-biological-macromolecules"      → True
    """
    slug = normalize(node.get("slug", ""))
    return slug.startswith(f"{num}-")


def _matches_by_name(node: dict, name: str | None) -> bool:
    """
    Match a node by exact name against its slug or plain-text title.

    Note: need to fix later or fully disarded if we no longer need it in the future.
    """
    if name is None:
        return False

    slug = normalize(node.get("slug", ""))
    plain_title = normalize(strip_html(node.get("title", "")))
    needle = normalize(name)

    # Strip leading label+number ("Unit 1 ", "Chapter 3 ") or bare number ("1 ")
    title_core = re.sub(r"^(\w+\s+)?\d+\s+", "", plain_title)
    # Strip a bare leading number from the needle ("1 Optics" -> "optics")
    needle_core = re.sub(r"^\d+\s+", "", needle)

    return (
        needle == slug
        or needle == plain_title
        or needle == title_core
        or needle_core == title_core
    )


def _matches_page_by_number(node: dict, page_num: str) -> bool:
    """
    Match a page/section node by its dotted section number, e.g. "2.1".
    """
    slug = normalize(node.get("slug", ""))
    prefix = page_num.strip().replace(".", "-") + "-"  # "2.1" → "2-1-"
    return slug.startswith(prefix)


# =========================
# input validator
# =========================


def _validate_inputs(
    unit_num, unit_name, chapter_num, chapter_name, page_num, page_name
):
    """
    Raise ValueError early if the caller provides conflicting or missing inputs.

    Exactly one of (unit_num, unit_name) must be provided.
    For chapter and page, providing both a number and a name is an error.
    page_num must look like a section number: digits and dots only ("2.1", "10", "3.4").
    """
    if unit_num is None and unit_name is None:
        raise ValueError("Provide either unit_num (int) or unit_name (str).")
    if unit_num is not None and unit_name is not None:
        raise ValueError("Provide unit_num OR unit_name, not both.")

    if chapter_num is not None and chapter_name is not None:
        raise ValueError("Provide chapter_num OR chapter_name, not both.")

    if page_num is not None and page_name is not None:
        raise ValueError("Provide page_num OR page_name, not both.")

    if page_num is not None and not re.fullmatch(r"\d+(\.\d+)?", str(page_num).strip()):
        raise ValueError(
            f"page_num must be a section number like '1', '2.1', or '10.3'."
            f" Got: '{page_num}'"
        )


# =========================
# Fetch the ABL catalog and find the book's uuid and commit sha
# =========================


def fetch_abl_catalog(abl_url: str) -> list:
    """
    Fetch the abl's content.
    """
    print(f"\n [1/5] Fetching ABL catalog")
    response = requests.get(abl_url, timeout=20)
    response.raise_for_status()
    catalog = response.json()
    n = len(catalog)
    print(f"      {n} books found in catalog")
    return catalog


_STOP_WORDS = {
    "of",
    "the",
    "and",
    "a",
    "an",
    "in",
    "for",
    "to",
    "by",
    "at",
    "vol",
    "volume",
}


def _key_tokens(s: str) -> frozenset:
    """Significant lowercase tokens from a title or slug, ignoring stop words."""
    return frozenset(re.findall(r"[a-z0-9]+", s.lower())) - _STOP_WORDS


def find_book(catalog: list, book_title: str) -> dict:
    """
    Find a book by title and return { title, book_uuid, commit_sha }.
    Accepts both ABL slugs ("principles-microeconomics-3e") and display
    names ("Principles of Microeconomics 3e") by falling back to
    stop-word-stripped token matching when substring search fails.
    """
    books = catalog
    if not books:
        raise ValueError("ABL catalog returned no books")

    print(f"[2/5] Searching {len(books)} books for: '{book_title}'")
    needle_tokens = _key_tokens(book_title)

    for book in books:
        slug = book.get("slug", "")
        # Fast path: direct substring match (works when caller passes a slug)
        if normalize(book_title) in normalize(slug):
            pass  # fall through to return below
        # Slow path: token-set equality (handles "Principles of Micro 3e" vs slug)
        elif needle_tokens and _key_tokens(slug) == needle_tokens:
            pass
        else:
            continue

        book_uuid = book.get("uuid")
        commit_sha = book.get("commit_sha")
        print(f"      ✓ Found : '{slug}'")
        print(f"        book_uuid  = {book_uuid}")
        print(f"        commit_sha = {commit_sha}\n")
        return {"title": slug, "book_uuid": book_uuid, "commit_sha": commit_sha[:7]}

    available = [book.get("slug") for book in books]
    raise ValueError(
        f"Book not found: '{book_title}'\n"
        f"Available titles (first 20):\n{json.dumps(available, indent=2)}"
    )


# =========================
# Fetch ToC
# =========================


def fetch_toc(book_info: dict) -> dict:
    """
    Build the ToC URL and fetch it.
    Prints a preview of top-level nodes so you can confirm the structure.
    """
    toc_url = build_url(TOC_URL_TEMPLATE, book_info)
    print(f"[3/5] Fetching ToC …\n      URL: {toc_url}")
    response = requests.get(toc_url, timeout=20)
    response.raise_for_status()
    toc = response.json()

    top_contents = toc.get("tree", {}).get("contents", [])
    print(f"      ToC fetched. Nodes under tree.contents: {len(top_contents)}")
    for node in top_contents[:8]:
        print(
            f"        [{node.get('toc_type','?')}]  "
            f"slug: '{node.get('slug','—')}'   "
            f"title: '{strip_html(node.get('title',''))}'"
        )
    return toc


# =========================
# Parse the ToC (unit → chapter → page)
# =========================


def find_unit_node(toc: dict, unit_num=None, unit_name=None) -> dict:
    """
    Find a unit node under toc["tree"]["contents"].
    Pass unit_num (int) OR unit_name (exact str), not both.
    """
    tree = toc.get("tree", toc)
    units = [n for n in (tree.get("contents") or []) if n.get("toc_type") == "unit"]

    for unit in units:
        hit = (
            _matches_by_number(unit, unit_num)
            if unit_num is not None
            else _matches_by_name(unit, unit_name)
        )
        if hit:
            print(f"  Unit   : '{strip_html(unit.get('title', ''))}'")
            return unit

    available = [
        f"  slug: '{u.get('slug','—')}'   title: '{strip_html(u.get('title',''))}'"
        for u in units
    ]
    label = (
        f"unit_num={unit_num}" if unit_num is not None else f"unit_name='{unit_name}'"
    )
    raise ValueError(
        f"Unit not found ({label})\nUnits available:\n" + "\n".join(available)
    )


def get_all_chapters(unit_node: dict) -> list[dict]:
    """Return every chapter node that is a direct child of a unit."""
    return [
        n for n in (unit_node.get("contents") or []) if n.get("toc_type") == "chapter"
    ]


def find_chapter_node(unit_node: dict, chapter_num=None, chapter_name=None) -> dict:
    """
    Find a chapter within a unit node.
    Pass chapter_num (int) OR chapter_name (exact str), not both.
    """
    chapters = get_all_chapters(unit_node)

    for ch in chapters:
        hit = (
            _matches_by_number(ch, chapter_num)
            if chapter_num is not None
            else _matches_by_name(ch, chapter_name)
        )
        if hit:
            print(f"  Chapter: '{strip_html(ch.get('title', ''))}'")
            return ch

    unit_title = strip_html(unit_node.get("title", "this unit"))
    available = [
        f"  slug: '{c.get('slug','—')}'   title: '{strip_html(c.get('title',''))}'"
        for c in chapters
    ]
    label = (
        f"chapter_num={chapter_num}"
        if chapter_num is not None
        else f"chapter_name='{chapter_name}'"
    )
    raise ValueError(
        f"Chapter not found ({label}) inside '{unit_title}'\n"
        f"Chapters available:\n" + "\n".join(available)
    )


def get_all_pages(
    chapter_node: dict, unit_title: str = "", chapter_title: str = ""
) -> list[dict]:
    """
    Collect every book-content page under a chapter that is in INCLUDE_TARGET_TYPES.

    Note that right now, it is unncessarily recursive. but can be adaptive later on
    if we want to include more context information in training process.
    """
    pages = []

    def visit(node: dict, path: list[str]):
        plain = strip_html(node.get("title", ""))
        children = node.get("contents") or []

        # omit the sub-book-content for now. (like chapter review).
        if (
            node.get("toc_type") == "book-content"
            and node.get("toc_target_type", "") in INCLUDE_TARGET_TYPES
        ):
            pages.append(
                {
                    "page_id": node.get("id").split("@", 1)[0],
                    "slug": node.get("slug", ""),
                    "title": plain,
                    "target_type": node.get("toc_target_type", ""),
                    "unit_title": unit_title,
                    "chapter_title": chapter_title,
                    "path": path + [plain],
                }
            )

        # recursion is not useful right now.
        for child in children:
            visit(child, path + [plain])

    visit(chapter_node, [strip_html(chapter_node.get("title", ""))])
    return pages


def find_page_node(
    chapter_node: dict,
    page_num=None,
    page_name=None,
    unit_title: str = "",
    chapter_title: str = "",
) -> dict:
    """
    Find one specific page within a chapter.
    Pass page_num (section number string, e.g. "2.1") OR page_name (exact str).
    """
    all_pages = get_all_pages(chapter_node, unit_title, chapter_title)

    for p in all_pages:
        # Re-use the original node dict for slug/title access inside matchers
        node = {"slug": p["slug"], "title": p["title"]}
        hit = (
            _matches_page_by_number(node, str(page_num))
            if page_num is not None
            else _matches_by_name(node, page_name)
        )
        if hit:
            print(f"  Page   : '{p['title']}'  (slug: {p['slug']})")
            return p

    ch_title = strip_html(chapter_node.get("title", "this chapter"))
    available = [f"  slug: '{p['slug']}'   title: '{p['title']}'" for p in all_pages]
    label = (
        f"page_num='{page_num}'" if page_num is not None else f"page_name='{page_name}'"
    )
    raise ValueError(
        f"Page not found ({label}) inside '{ch_title}'\n"
        f"Pages available:\n" + "\n".join(available)
    )


def resolve_pages(
    toc: dict,
    unit_num: int | None = None,
    unit_name: str | None = None,
    chapter_num: int | None = None,
    chapter_name: str | None = None,
    page_num: str | None = None,
    page_name: str | None = None,
) -> list[dict]:
    """
    Return a flat list of ToC page dicts based on which fields are supplied.

      unit only              → all pages in every chapter of that unit
      unit + chapter         → all pages in that one chapter
      unit + chapter + page  → that single page
    """
    _validate_inputs(
        unit_num, unit_name, chapter_num, chapter_name, page_num, page_name
    )
    print(f"[4/5] Resolving pages …")
    unit_label = f"num={unit_num}" if unit_num is not None else f"name='{unit_name}'"
    chapter_label = (
        f"num={chapter_num}"
        if chapter_num is not None
        else f"name='{chapter_name}'" if chapter_name is not None else "(all)"
    )
    page_label = (
        f"num='{page_num}'"
        if page_num is not None
        else f"name='{page_name}'" if page_name is not None else "(all)"
    )
    print(f"      unit    = {unit_label}")
    print(f"      chapter = {chapter_label}")
    print(f"      page    = {page_label}\n")

    unit_node = find_unit_node(toc, unit_num=unit_num, unit_name=unit_name)
    unit_title = strip_html(unit_node.get("title", ""))

    need_chapter = chapter_num is not None or chapter_name is not None
    chapters = (
        [
            find_chapter_node(
                unit_node, chapter_num=chapter_num, chapter_name=chapter_name
            )
        ]
        if need_chapter
        else get_all_chapters(unit_node)
    )
    print(f"      → {len(chapters)} chapter(s) to process")

    need_page = page_num is not None or page_name is not None
    result: list[dict] = []
    for ch_node in chapters:
        ch_title = strip_html(ch_node.get("title", ""))
        if need_page:
            result.append(
                find_page_node(
                    ch_node,
                    page_num=page_num,
                    page_name=page_name,
                    unit_title=unit_title,
                    chapter_title=ch_title,
                )
            )
        else:
            result.extend(get_all_pages(ch_node, unit_title, ch_title))

    print(f"      → {len(result)} page(s) selected\n")
    return result


# =========================
# Fetch and parse each page
# =========================


def fetch_page_xhtml(book_info: dict, page_id: str) -> str:
    """Fetch one XHTML page and return its raw text."""
    url = build_url(PAGE_URL_TEMPLATE, {**book_info, "page_id": page_id})
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return response.text


def parse_page_xhtml(xhtml: str, page_meta: dict) -> dict:
    """
    Parse an XHTML page and extract title, learning objectives, body text, figures.
    """
    soup = BeautifulSoup(xhtml, "lxml")

    # Remove noise
    for tag in soup(["script", "nav", "style", "head"]):
        tag.decompose()

    # Strip hyperlinks, keep visible text
    for a in soup.find_all("a"):
        a.replace_with(a.get_text())

    # Replace images with alt text, or remove if no alt
    for img in soup.find_all("img"):
        alt = img.get("alt", "").strip()
        if alt:
            img.replace_with(alt)
        else:
            img.decompose()

    # Convert the cleaned body to Markdown
    body = soup.find("body") or soup
    markdown = md(str(body), heading_style="ATX", bullets="-")

    return {
        "page_id": page_meta["page_id"],
        "markdown": markdown.strip(),
    }


# =========================
# Entry point
# =========================


def crawl(
    book_title: str,
    unit_num: int | None = None,
    unit_name: str | None = None,
    chapter_num: int | None = None,
    chapter_name: str | None = None,
    page_num: str | None = None,
    page_name: str | None = None,
) -> dict:
    """
    End-to-end crawl. For each level provide the number OR the exact name.

    unit_num / unit_name      required — exactly one must be given
    chapter_num / chapter_name  optional — omit to crawl all chapters in the unit
    page_num / page_name        optional — omit to crawl all pages in the chapter(s)

    page_num format: dotted section number, e.g. "1", "2.1", "10.3"
    """
    _validate_inputs(
        unit_num, unit_name, chapter_num, chapter_name, page_num, page_name
    )

    catalog = fetch_abl_catalog(ABL_URL)
    book_info = find_book(catalog, book_title)
    toc = fetch_toc(book_info)
    toc_pages = resolve_pages(
        toc,
        unit_num=unit_num,
        unit_name=unit_name,
        chapter_num=chapter_num,
        chapter_name=chapter_name,
        page_num=page_num,
        page_name=page_name,
    )

    print(f"[5/5] Fetching and parsing {len(toc_pages)} page(s) …")
    parsed_pages = []
    for i, toc_page in enumerate(toc_pages, 1):
        label = f"{toc_page['chapter_title']} / {toc_page['title']}"
        print(f"      [{i:>2}/{len(toc_pages)}] {label}")
        try:
            xhtml = fetch_page_xhtml(book_info, toc_page["page_id"])
            parsed = parse_page_xhtml(xhtml, toc_page)
            parsed_pages.append(parsed)
            print(f"             {len(parsed['markdown'].split())} words")
        except Exception as e:
            print(f"             FAILED: {e}  (skipping)")

    return {
        "book_title": book_info["title"],
        "book_uuid": book_info["book_uuid"],
        "commit_sha": book_info["commit_sha"],
        "unit_num": unit_num,
        "unit_name": unit_name,
        "chapter_num": chapter_num,
        "chapter_name": chapter_name,
        "page_num": page_num,
        "page_name": page_name,
        "pages": parsed_pages,
    }


if __name__ == "__main__":
    BOOK_TITLE = "university-physics-volume-1"

    # Provide a number OR a name for each level, but not both.
    UNIT_NUM = 1
    UNIT_NAME = None
    CHAPTER_NUM = 1
    CHAPTER_NAME = None
    PAGE_NUM = None
    PAGE_NAME = None  # e.g. PAGE_NUM = "1.1"

    result = crawl(
        BOOK_TITLE,
        unit_num=UNIT_NUM,
        unit_name=UNIT_NAME,
        chapter_num=CHAPTER_NUM,
        chapter_name=CHAPTER_NAME,
        page_num=PAGE_NUM,
        page_name=PAGE_NAME,
    )

    # Merge all pages into one Markdown file
    merged = "\n\n---\n\n".join(p["markdown"] for p in result["pages"])

    # Build a more descriptive name
    def _slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

    parts = [_slugify(BOOK_TITLE)]
    if UNIT_NUM is not None:
        parts.append(f"unit-{UNIT_NUM}")
    elif UNIT_NAME is not None:
        parts.append(f"unit-{_slugify(UNIT_NAME)}")
    if CHAPTER_NUM is not None:
        parts.append(f"ch-{CHAPTER_NUM}")
    elif CHAPTER_NAME is not None:
        parts.append(f"ch-{_slugify(CHAPTER_NAME)}")
    if PAGE_NUM is not None:
        parts.append(f"p-{PAGE_NUM}")
    elif PAGE_NAME is not None:
        parts.append(f"p-{_slugify(PAGE_NAME)}")

    # Make relative position in the project folder
    PROJECT_DIR = Path(__file__).resolve().parent
    output_dir = PROJECT_DIR / "TextbookContext"
    # output_dir.mkdir(exist_ok=True)

    md_path = output_dir / f"{'_'.join(parts)}.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)

    print(f"\n  Done. Output saved to: {md_path}")
