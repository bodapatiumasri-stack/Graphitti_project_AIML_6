

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from kg_builder import KGBuilder
from retrieval import RetrievalEngine
from llm import generate_answer
app = FastAPI(title="Graphitti Mid-Eval API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

kg  = KGBuilder()
ret = RetrievalEngine(kg)


# ── Request models ─────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    url: str
    page_title: Optional[str] = ""
    entities: list[dict]     
    relationships: list[dict]  
    raw_text: str              # cleaned page text

class QueryRequest(BaseModel):
    question: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(data: IngestRequest):
    try:
        result = kg.build_or_update(
            url=data.url,
            entities=data.entities,
            relationships=data.relationships,
            raw_text=data.raw_text,
            page_title=data.page_title,
        )
        ret.index(url=data.url, text=data.raw_text, title=data.page_title)
        return {
            "status": "success",
            "url": data.url,
            "nodes_added": result["nodes_added"],
            "relationships_added": result["relationships_added"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
def query(req: QueryRequest):
    try:
        context, sources, graph_nodes = ret.retrieve_all(query=req.question)
        answer = generate_answer(query=req.question, context=context)
        return {
            "answer": answer,
            "sources": sources,
            "graph_nodes_used": graph_nodes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
