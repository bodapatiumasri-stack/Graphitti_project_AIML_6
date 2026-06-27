import spacy
from pathlib import Path

import spacy
import requests
from pathlib import Path

nlp = spacy.load("en_core_web_sm")

# Read URL
urls_file = Path(__file__).parent/ "playwright" / "urls.txt"
url = urls_file.read_text(encoding="utf-8").splitlines()[0]

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

# Extract relationships (subject-verb-object)
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

# Send to your backend
response = requests.post("http://localhost:8000/ingest", json={
    "url": url,
    "page_title": page_title,
    "entities": entities,
    "relationships": relationships,
    "raw_text": text
})

print(f"Ingest status: {response.status_code}")
print(f"Response: {response.json()}")