import spacy
from pathlib import Path

nlp = spacy.load("en_core_web_sm")

input_file = Path(__file__).parent.parent / "bs4" / "cleaned_result.txt"

output_file = Path(__file__).parent / "entity_list.txt"

with open(input_file, "r", encoding="utf-8") as f:
    text = f.read()

doc = nlp(text)

entity_list = []

for ent in doc.ents:
    entity_list.append({
        "text": ent.text,
        "label": ent.label_
    })

with open(output_file, "w", encoding="utf-8") as f:
    f.write(str(entity_list))

print("Entity list saved successfully.")
