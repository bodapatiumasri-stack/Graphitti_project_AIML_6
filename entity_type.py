import spacy
from pathlib import Path

import spacy
import requests
from pathlib import Path

nlp = spacy.load("en_core_web_sm")

# Read URL
urls_file = Path(__file__).parent / "playwright" / "urls.txt"

# Track the current index using a file so it remembers across terminal runs
counter_file = Path(__file__).parent / "counter.txt"
if not counter_file.exists():
    counter_file.write_text("0")

# Load the current index value
urls_crawled = int(counter_file.read_text().strip())

# Read the lines and grab the current URL based on our variable
all_urls = urls_file.read_text(encoding="utf-8").splitlines()

# Prevent crashing if we run out of URLs
if urls_crawled < len(all_urls):
    url = all_urls[urls_crawled]
    counter_file.write_text(str(urls_crawled + 1))
else:
    print("All URLs have already been processed! Resetting counter.")
    counter_file.write_text("0")
    url = all_urls[0]

# Read cleaned text
input_file = Path(__file__).parent/ "cleaned_result.txt"
text = input_file.read_text(encoding="utf-8")

# Read page title
result_file = Path(__file__).parent.parent / "playwright" / "result.txt"
page_title = url.split("/")[-1].replace("-", " ").title()

doc = nlp(text)

# Extract entities
entities = []
for ent in doc.ents:
    entities.append({
        "text": ent.text,
        "label": ent.label_
    })

# Extract relationships 
relationships = []
for token in doc:
    if token.dep_ == "ROOT":
        subject = None
        obj = None
        for child in token.children:
            if child.dep_ in ("nsubj", "nsubjpass"):
                subject = child.text
            if child.dep_ in ("dobj", "attr", "prep"):
                obj = child.text
        if subject and obj:
            relationships.append({
                "source": subject,
                "relation": token.lemma_.upper(),
                "target": obj
            })

print(f"Entities found: {len(entities)}")
print(f"Relationships found: {len(relationships)}")

response = requests.post("http://localhost:8000/ingest", json={
    "url": url,
    "page_title": page_title,
    "entities": entities,
    "relationships": relationships,
    "raw_text": text
})

print(f"Ingest status: {response.status_code}")
print(f"Response: {response.json()}")
