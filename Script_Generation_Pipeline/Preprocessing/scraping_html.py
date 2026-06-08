# ...existing code...
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import requests

website = "https://openstax.org/apps/archive/20260407.195030/contents/06aba565-9432-40f6-97ee-b8a361f118a8@ee086d3:4ffb3e5b-9fb7-46e5-9928-20802d505e38.xhtml"

response = requests.get(website)
response.raise_for_status()  # Check if the request was successful

html = response.text
soup = BeautifulSoup(html, "html.parser")

# remove external hyperlinks but keep their visible text
for a in soup.find_all("a"):
    href = a.get("href", "")
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

# Save the markdown output to a file
output_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.4.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(body_md)
