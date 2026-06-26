from bs4 import BeautifulSoup
from pathlib import Path
import re

input_file = Path(__file__).parent.parent / "playwright" / "result.txt"

output_file = Path(__file__).parent / "cleaned_result.txt"

with open(input_file, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

for tag in soup(["script", "style", "noscript"]):
    tag.decompose()

text = soup.get_text(separator=" ")
text = re.sub(r"\s+", " ", text).strip()

with open(output_file, "w", encoding="utf-8") as f:
    f.write(text)

print("Cleaned text saved to cleaned_result.txt")