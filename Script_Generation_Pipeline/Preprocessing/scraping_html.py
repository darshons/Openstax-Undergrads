# ...existing code...
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import requests

website = "https://openstax.org/apps/archive/20260407.195030/contents/06aba565-9432-40f6-97ee-b8a361f118a8@ee086d3:1db17970-a37e-48e8-b20c-941b52ce73ef.xhtml"

response = requests.get(website)
response.raise_for_status()  # Check if the request was successful

html = response.text
soup = BeautifulSoup(html, "html.parser")

# remove external hyperlinks but keep their visible text
for a in soup.find_all("a"):
    href = a.get("href", "")
    if href.startswith(("http://", "https://", "//")):
        a.replace_with(a.get_text())

# remove external images (replace with alt text if present, otherwise remove)
for img in soup.find_all("img"):
    src = img.get("src", "")
    if src.startswith(("http://", "https://", "//", "../")):
        alt = img.get("alt", "")
        if alt:
            img.replace_with(alt)
        else:
            img.decompose()

body = soup.find("body")
body_html = str(body)
body_md = md(body_html)
print(body_md)
