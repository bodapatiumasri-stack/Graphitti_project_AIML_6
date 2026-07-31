import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import time

folder = Path("playwright")
folder.mkdir(exist_ok=True)
urls_file = folder / "urls.txt"
depth_file = folder / "depth.txt"
result_file = folder / "result.txt"

def extract_content():
    url = ""
    if urls_file.exists():
        lines = [line.strip() for line in urls_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines: url = lines[-1]

    if not url:
        url = "https://www.webmd.com/arthritis/default.htm"

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    MAX_DEPTH = 1
    if depth_file.exists():
        try:
            d = depth_file.read_text(encoding="utf-8").strip()
            if d in ("1", "2"): MAX_DEPTH = int(d)
        except: MAX_DEPTH = 1

    print(f"Crawling: {url} (depth {MAX_DEPTH})")
    crawled_urls = set()

    def get_internal_links(page, base_url):
        base_domain = urlparse(base_url).netloc
        try:
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        except: return []
        internal = []
        for link in links:
            try:
                parsed = urlparse(link)
                if (parsed.netloc == base_domain and link not in crawled_urls 
                    and not link.endswith((".pdf", ".jpg", ".png")) and "#" not in link):
                    internal.append(link)
            except: pass
        return list(set(internal))[:5]

    def crawl_target(page, target_url, current_depth):
        if target_url in crawled_urls or current_depth > MAX_DEPTH: return
        print(f"  [depth {current_depth}] Fetching: {target_url}")
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            html = page.content()
            
            with open(result_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n<!-- URL: {target_url} -->\n{html}")
                
            crawled_urls.add(target_url)
            if current_depth < MAX_DEPTH:
                links = get_internal_links(page, target_url)
                for link in links:
                    crawl_target(page, link, current_depth + 1)
        except Exception as e:
            print(f"Playwright error on {target_url}: {e}")

    result_file.write_text("", encoding="utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            crawl_target(page, url, current_depth=1)
            browser.close()
    except Exception as err:
        print(f"Playwright engine failed ({err}). Using fallback HTTP Requests...")
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            if res.status_code == 200:
                result_file.write_text(f"<!-- URL: {url} -->\n{res.text}", encoding="utf-8")
        except Exception as req_err:
            print(f"Fallback failed: {req_err}")

    print(f"Extracted content saved to {result_file}")

if __name__ == "__main__":
    extract_content()
