import os
import re
from pathlib import Path
from bs4 import BeautifulSoup

folder = Path("playwright")
result_file = folder / "result.txt"
cleaned_file = folder / "cleaned_text.txt"
title_file = folder / "page_title.txt"
cleaned_dir = folder / "cleaned_texts"
cleaned_dir.mkdir(exist_ok=True)

def clean_html():
    if not result_file.exists():
        print("result.txt not found!")
        return

    raw_content = result_file.read_text(encoding="utf-8")
    if not raw_content.strip():
        print("result.txt is empty!")
        return

    soup_main = BeautifulSoup(raw_content, "html.parser")
    page_title = ""
    if soup_main.title and soup_main.title.string:
        page_title = soup_main.title.string.strip()
    title_file.write_text(page_title, encoding="utf-8")

    pages = raw_content.split("<!-- URL: ")
    all_cleaned = []

    for page in pages:
        if not page.strip():
            continue

        lines = page.split("-->", 1)
        if len(lines) == 2:
            page_url = lines[0].strip()
            page_html = lines[1]
        else:
            page_url = "unknown_page"
            page_html = page

        soup = BeautifulSoup(page_html, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form", "iframe", "button", "noscript"]):
            tag.decompose()

        clean_text = soup.get_text(separator=" ", strip=True)
        clean_text = re.sub(r'\s+', ' ', clean_text)

        if len(clean_text) > 100:
            all_cleaned.append(clean_text)

            file_name = page_url.replace("https://", "").replace("http://", "").replace("/", "_").replace("?", "_")[:60] + ".txt"
            per_page_path = cleaned_dir / file_name
            per_page_path.write_text(f"URL: {page_url}\n\n{clean_text}", encoding="utf-8")
            print(f" Saved clean page text to {per_page_path}")

    master_text = "\n\n".join(all_cleaned)
    cleaned_file.write_text(master_text, encoding="utf-8")
    print(f" HTML Cleaned. Title: '{page_title}'. Saved {len(master_text)} characters to {cleaned_file}")

if __name__ == "__main__":
    clean_html()
