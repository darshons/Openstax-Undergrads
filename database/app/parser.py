import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# Map textbook → chapter → OpenStax content URL.
# Add entries here as more chapters are needed for the prototype.
CHAPTER_URLS: dict = {
    "Clinical Nursing": {
        "Chapter 1: Patient Assessment": (
            "https://openstax.org/apps/archive/20260407.195030/contents/"
            "06aba565-9432-40f6-97ee-b8a361f118a8@ee086d3:"
            "1db17970-a37e-48e8-b20c-941b52ce73ef.xhtml"
        ),
    },
}


def _scrape_url(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a"):
        a.replace_with(a.get_text())

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith(("http://", "https://", "//", "../")):
            alt = img.get("alt", "")
            if alt:
                img.replace_with(alt)
            else:
                img.decompose()

    body = soup.find("body")
    return md(str(body)) if body else ""


def parse_chapters_to_markdown(textbook: str, chapters: list) -> str:
    """Scrape OpenStax HTML for each chapter and return combined markdown."""
    parts = []
    for chapter in chapters:
        url = CHAPTER_URLS.get(textbook, {}).get(chapter)
        if not url:
            parts.append(f"## {chapter}\n\n[Content URL not yet configured for this chapter]")
            continue
        try:
            content = _scrape_url(url)
            parts.append(f"## {chapter}\n\n{content}")
        except Exception as exc:
            parts.append(f"## {chapter}\n\n[Scrape failed: {exc}]")
    return "\n\n---\n\n".join(parts) if parts else ""
