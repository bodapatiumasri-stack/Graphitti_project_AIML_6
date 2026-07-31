# Graphitti – Graph-Native Web Intelligence

Graphitti is an intelligent web exploration platform thattransforms website content into a structured knowledge
network.

Instead of treating webpages as isolated documents, the system organizes important concepts and their relationships
into an interconnected graph. Users can explore website content more efficiently, ask questions in natural language,
and receive AI-generated responses based on the extracted knowledge.

The platform also provides an interactive graph visualization, making it easier to understand how different
concepts are connected.

---

## Why Graphitti?

Searching large websites can be time-consuming, especially when information is spread across multiple pages.

Graphitti solves this problem by organizing webpage content into a structured knowledge graph. Instead of reading every
page, users can ask questions directly and receive relevant,context-aware answers.

---

## Features

- Automatic website crawling from a user-provided URL
- Extraction of meaningful information from webpage content
- Identification of entities and their relationships
- Automatic construction of a Knowledge Graph
- AI-powered chatbot for natural language interaction
- Hybrid retrieval using semantic, keyword, and graph search
- Interactive Knowledge Graph visualization
- Reusable knowledge graphs for processed websites
- Efficient information retrieval with optimized indexing

---

## How It Works

1. The user enters a website URL.
2. The system crawls the webpages.
3. HTML content is cleaned and processed.
4. Entities and relationships are extracted.
5. A Knowledge Graph is created and stored.
6. Semantic data is indexed for retrieval.
7. Users ask questions in natural language.
8. The system retrieves the most relevant context.
9. The language model generates an accurate answer.
10. The graph visualization displays the connected knowledge.

---

## Technology Stack
### Frontend
HTML
CSS
JavaScript
### Backend
FastAPI
Programming Language
Python
### Web Crawling
Playwright
### Entity Extraction
GLiNER
### Relationship Extraction
spaCy
### Databases
Neo4j
ChromaDB
### Retrieval Techniques
Graph Search
Vector Search
BM25 Keyword Search
### Language Model
Groq API (Llama 3.3 70B)
### Deployment
we deployed in Railway but due to some errors only html code is applying

---

## Installation

### Clone the repository

```bash
git clone https://github.com/bodapatiumasri-stack/Graphitti_project_AIML_6.git
```

### Move into the project directory

```bash
cd Graphitti_project_AIML_6
```

### Install the required dependencies

```bash
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file in the project root and add the required API keys and database credentials.

### Run the application

Using Python:

```bash
python main.py
```

Or using Uvicorn:

```bash
uvicorn main:app --reload
```

---

## Usage

1. Launch the application.
2. Enter the URL of the website you want to analyze.
3. Wait for the system to process the website.
4. Ask questions related to the website content.
5. View AI-generated responses and explore the Knowledge Graph.

---

## Team
### **Bodapati Uma Sri**

**Contribution:**

* LLM integration
* Multi-agent orchestration
* FastAPI backend development
* Hybrid retrieval methods

### **Keetha Akshaya**

**Contribution:**

* Website content extraction
* Content cleaning and preprocessing
* Named Entity Recognition (NER)
* Knowledge Graph (KG) construction

### **Dharavath Mamatha**

**Contribution:**

* Frontend development using HTML, CSS, and JavaScript
* User interface design and implementation


---

## Acknowledgement

This project was developed as part of **IITISoC 2026** with the objective of building an intelligent graph-based system 
for web information exploration and question answering. It demonstrates the integration of web crawling, natural language processing,
knowledge graph construction, hybrid retrieval, and large language models into a unified platform.

---
