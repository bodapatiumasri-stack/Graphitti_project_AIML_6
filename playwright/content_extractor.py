from pathlib import Path
from playwright.sync_api import sync_playwright

url = input("Enter URL: ")

folder = Path("playwright")
folder.mkdir(exist_ok=True)

result_file = folder / "result.txt"
urls_file = folder / "urls.txt"

if urls_file.exists():
    urls = urls_file.read_text(encoding="utf-8").splitlines()
else:
    urls = []


if url in urls:
    print("Website already crawled.")
    print("Skipping Playwright.")
else:
    print("Starting Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        html = page.content()

        browser.close()

    result_file.write_text(html, encoding="utf-8")

    with urls_file.open("a", encoding="utf-8") as f:
        f.write(url + "\n")

    print("Website crawled successfully.")
    print("HTML saved in result.txt")