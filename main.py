import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from kg_builder import KGBuilder
from retrieval import RetrievalEngine
from orchestrator import OrchestratorAgent
from llm import generate_answer


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_chat_histories_from_disk()
    _load_crawled_sources_from_disk()

    if kg.verify_connection():
        print("Neo4j connected! Reconciling with persistent sources...")
        _load_sources_from_neo4j()
    else:
        print("Warning: Could not verify active Neo4j connection.")
    yield
    if hasattr(kg, "close"):
        kg.close()

app = FastAPI(title="Graphitti Medical AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

kg           = KGBuilder()
ret          = RetrievalEngine(kg)
orchestrator = OrchestratorAgent(ret)

chat_histories: Dict[str, List[Dict[str, str]]] = {}
crawled_sources: Dict[str, dict] = {}

CHAT_HISTORY_FILE     = os.path.join(os.getcwd(), "chat_histories.json")
CRAWLED_SOURCES_FILE  = os.path.join(os.getcwd(), "crawled_sources.json")


def _load_chat_histories_from_disk():
    global chat_histories
    if not os.path.exists(CHAT_HISTORY_FILE):
        return
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            chat_histories = json.load(f)
        print(f"Loaded {len(chat_histories)} chat(s) from disk")
    except Exception as e:
        print(f"Warning loading chat_histories from disk: {e}")


def _save_chat_histories_to_disk():
    try:
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(chat_histories, f)
    except Exception as e:
        print(f"Warning saving chat_histories to disk: {e}")


def _load_crawled_sources_from_disk():
    global crawled_sources
    if not os.path.exists(CRAWLED_SOURCES_FILE):
        return
    try:
        with open(CRAWLED_SOURCES_FILE, "r", encoding="utf-8") as f:
            crawled_sources = json.load(f)
        print(f"Loaded {len(crawled_sources)} source(s) from disk (depth preserved)")
    except Exception as e:
        print(f"Warning loading crawled_sources from disk: {e}")


def _save_crawled_sources_to_disk():
    try:
        with open(CRAWLED_SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(crawled_sources, f)
    except Exception as e:
        print(f"Warning saving crawled_sources to disk: {e}")



class IngestRequest(BaseModel):
    url: str
    page_title: Optional[str] = ""
    entities: list[dict]
    relationships: list[dict]
    raw_text: str

class QueryRequest(BaseModel):
    question: str
    chat_id: Optional[str] = "default"

class CrawlRequest(BaseModel):
    url: str
    depth: Optional[int] = 1



def _is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def _is_reachable_url(url: str, timeout: float = 6.0) -> tuple[bool, str]:
    headers = {"User-Agent": "Mozilla/5.0 (Graphitti crawler validation)"}
    try:
        requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        return True, ""
    except requests.exceptions.SSLError:
        return False, "SSL certificate error — the site's certificate could not be verified."
    except requests.exceptions.ConnectionError:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
            resp.close()
            return True, ""
        except requests.exceptions.RequestException:
            return False, "Could not connect — the domain may not exist or is refusing connections."
    except requests.exceptions.Timeout:
        return False, f"The site did not respond within {timeout:.0f}s."
    except requests.exceptions.RequestException as e:
        return False, f"Could not reach URL: {e}"


def _extract_topic_title(url: str, raw_title: str = "") -> str:
    """Extracts a clean, human-readable webpage topic title for UI sidebar tags."""
    if raw_title and "webmd.com" not in raw_title.lower() and len(raw_title) > 3:
        clean = raw_title.split("|")[0].split("-")[0].replace("WebMD", "").replace("webmd", "").strip(" |:-")
        if len(clean) > 3:
            return clean.title()

    parts = [p for p in url.split("/") if p and not p.startswith("http") and "webmd.com" not in p]
    if parts:
        slug = parts[-1].replace("-", " ").replace(".htm", "").replace(".html", "").replace("default", "")
        if not slug and len(parts) > 1:
            slug = parts[-2].replace("-", " ")
        if slug and len(slug) > 2:
            return slug.title()

    return url.replace("https://", "").replace("http://", "").split("/")[0]


def _load_sources_from_neo4j():
    if not kg.driver:
        return
    try:
        with kg.driver.session() as s:
            res = s.run("""
                MATCH (p:Page)
                OPTIONAL MATCH (p)-[:MENTIONS]->(e:Entity)
                RETURN p.url AS url, p.title AS title, count(DISTINCT e) AS node_count
            """)
            added = 0
            for r in res:
                u = r["url"]
                if u in crawled_sources:
                    continue
                t = r["title"] or _extract_topic_title(u)
                crawled_sources[u] = {
                    "url": u, "title": t, "status": "completed",
                    "node_count": r["node_count"], "depth": 1
                }
                added += 1
        if added:
            _save_crawled_sources_to_disk()
        print(f"Ready: {len(crawled_sources)} total source(s) tracked ({added} newly discovered from Neo4j)")
    except Exception as e:
        print(f"Warning loading sources from Neo4j: {e}")


def _save_chat(chat_id: str, question: str, answer: str):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    chat_histories[chat_id].append({
        "question": question,
        "answer":   answer,
        "time":     datetime.utcnow().isoformat()
    })
    _save_chat_histories_to_disk()


def _get_chat_history_for_llm(chat_id: str) -> List[Dict[str, str]]:

    formatted = []
    for turn in chat_histories.get(chat_id, []):
        formatted.append({"role": "user", "content": turn["question"]})
        formatted.append({"role": "assistant", "content": turn["answer"]})
    return formatted


def _run_crawl_pipeline(url: str, depth: int = 1):
    """Executes scraper -> cleaner -> entity_type.py pipeline."""
    try:
        os.makedirs("playwright/cleaned_texts", exist_ok=True)
        with open("playwright/urls.txt", "w", encoding="utf-8") as f:
            f.write(url)
        with open("playwright/depth.txt", "w", encoding="utf-8") as f:
            f.write(str(depth))

        python_bin = sys.executable
        cwd = os.getcwd()
        print(f"Starting crawl pipeline for {url} (depth={depth})...")

        subprocess.run([python_bin, "content_extractor.py"], cwd=cwd, check=True)
        subprocess.run([python_bin, "html_cleaner.py"], cwd=cwd, check=True)
        subprocess.run([python_bin, "entity_type.py"], cwd=cwd, check=True)

        print(f"Pipeline executed successfully for {url}")
    except Exception as e:
        print(f"Crawl pipeline exception for {url}: {e}")
        if url in crawled_sources:
            crawled_sources[url]["status"] = "failed"
            _save_crawled_sources_to_disk()


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(os.getcwd(), "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>Graphitti Backend is running!</h2>")


@app.get("/health")
def health():
    stats = kg.get_all_stats()
    return {
        "status": "ok" if kg.verify_connection() else "neo4j_disconnected",
        "timestamp": datetime.utcnow().isoformat(),
        "total_nodes": stats.get("nodes", 0),
        "total_relationships": stats.get("relationships", 0),
        "total_sources": len(crawled_sources)
    }


@app.post("/query")
def query(req: QueryRequest):
    """Medical Chatbot endpoint with Retrieval-Augmented Generation & Memory."""
    try:
        chat_id = req.chat_id or "default"
        formatted_history = _get_chat_history_for_llm(chat_id)

        clean_q = req.question.lower().strip()
        greetings = ["hi", "hello", "hey", "hii", "helo", "hai", "greetings"]
        if clean_q in greetings and not formatted_history:
            answer = "Hello! I am Graphitti, your Graph-Native Medical Assistant. Ask me any medical question or add a website URL to expand my knowledge!"
            _save_chat(chat_id, req.question, answer)
            return {
                "question": req.question,
                "answer": answer,
                "sources": [],
                "graph_nodes_used": [],
                "strategy": "greeting",
                "has_information": True
            }

        result = orchestrator.run(req.question)
        context = result.get("context", "")
        has_information = bool(context and len(context.strip()) > 30)

        if not has_information and not formatted_history:
            answer = "I don't have enough information about this topic in my knowledge base yet. Click '+ Add website' above to add a source!"
        else:
            answer = generate_answer(
                query=req.question,
                context=context,
                chat_history=formatted_history
            )

        _save_chat(chat_id, req.question, answer)
        return {
            "question":         req.question,
            "answer":           answer,
            "sources":          result.get("sources", []),
            "graph_nodes_used": result.get("graph_nodes", []),
            "strategy":         result.get("strategy", "tri_hybrid_rag"),
            "has_information":  has_information
        }
    except Exception as e:
        print(f"[Query Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/crawl")
def crawl(req: CrawlRequest, background_tasks: BackgroundTasks):
    try:
        url_clean = req.url.strip()

        if not url_clean:
            raise HTTPException(status_code=400, detail="URL cannot be empty.")
        if not _is_valid_url(url_clean):
            raise HTTPException(
                status_code=400,
                detail=f"'{url_clean}' isn't a valid URL. Include the scheme, e.g. https://www.webmd.com/..."
            )

        reachable, reason = _is_reachable_url(url_clean)
        if not reachable:
            raise HTTPException(
                status_code=400,
                detail=f"Can't crawl '{url_clean}': {reason}"
            )

        depth_val = req.depth if req.depth in [1, 2] else 1
        display_title = _extract_topic_title(url_clean)

        existing = crawled_sources.get(url_clean)
        existing_depth = existing.get("depth", 1) if existing else 0
        if existing and existing.get("status") == "completed" and existing_depth >= depth_val:
            return {
                "status": "already_crawled",
                "url": url_clean,
                "depth": existing_depth,
                "title": existing.get("title", display_title),
                "message": f"Website '{existing.get('title', display_title)}' is already in your Knowledge Graph (depth {existing_depth})!"
            }
        if kg.driver and depth_val <= existing_depth:
            try:
                with kg.driver.session() as s:
                    res = s.run("MATCH (p:Page) WHERE toLower(p.url) = toLower($url) RETURN p LIMIT 1", url=url_clean)
                    if res.single():
                        crawled_sources[url_clean] = {
                            "title": display_title, "url": url_clean,
                            "status": "completed", "depth": existing_depth
                        }
                        _save_crawled_sources_to_disk()
                        return {
                            "status": "already_crawled",
                            "url": url_clean,
                            "depth": existing_depth,
                            "title": display_title,
                            "message": f"Website '{display_title}' is already in your Knowledge Graph!"
                        }
            except Exception:
                pass

        crawled_sources[url_clean] = {
            "title":      display_title,
            "url":        url_clean,
            "crawled_at": datetime.utcnow().isoformat(),
            "node_count": 0,
            "status":     "crawling",
            "depth":      depth_val
        }
        _save_crawled_sources_to_disk()

        background_tasks.add_task(_run_crawl_pipeline, url_clean, depth_val)
        return {
            "status":  "started",
            "url":     url_clean,
            "depth":   depth_val,
            "title":   display_title
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/status")
def status(url: str):
    """Check crawling status of a specific URL."""
    url_clean = url.strip()
    source = crawled_sources.get(url_clean)
    if not source:
        for k, v in crawled_sources.items():
            if url_clean in k or k in url_clean:
                source = v
                break
    curr_status = source.get("status", "completed") if source else "completed"
    return {
        "url":          url,
        "status":       curr_status,
        "crawl_status": curr_status,
        "last_crawled": source.get("crawled_at") if source else None,
        "node_count":   source.get("node_count", 0) if source else 0,
        "depth":        source.get("depth", 1) if source else 1
    }


@app.get("/sources")
def get_sources():
    if len(crawled_sources) == 0:
        _load_crawled_sources_from_disk()
    if len(crawled_sources) == 0:
        _load_sources_from_neo4j()
    sources = [
        {
            "url":        k,
            "title":      v.get("title") or _extract_topic_title(k),
            "crawled_at": v.get("crawled_at", ""),
            "status":     v.get("status", "completed"),
            "node_count": v.get("node_count", 0),
            "depth":      v.get("depth", 1)
        }
        for k, v in crawled_sources.items()
    ]
    return {"sources": sources, "total": len(sources)}
@app.delete("/sources")
def delete_source(url: str):
    if url in crawled_sources:
        del crawled_sources[url]
        _save_crawled_sources_to_disk()
        return {"status": "success", "url": url}
    return {"status": "not_found"}
@app.post("/ingest")
def ingest(data: IngestRequest):
    """Ingests NLP entities and relationships into Neo4j & ChromaDB."""
    try:
        result = kg.build_or_update(
            url=data.url,
            entities=data.entities,
            relationships=data.relationships,
            raw_text=data.raw_text,
            page_title=data.page_title,
        )
        ret.index(url=data.url, text=data.raw_text, title=data.page_title)

        nodes_added = result.get("nodes_added", len(data.entities))

        current_depth = crawled_sources.get(data.url, {}).get("depth", 1)
        clean_title = _extract_topic_title(data.url, data.page_title)

        crawled_sources[data.url] = {
            "title":      clean_title,
            "url":        data.url,
            "crawled_at": datetime.utcnow().isoformat(),
            "node_count": nodes_added,
            "status":     "completed",
            "depth":      current_depth
        }
        _save_crawled_sources_to_disk()

        print(f"✅ Ingestion successful for {data.url} ({nodes_added} nodes)")
        return {"status": "success", "url": data.url, "nodes_added": nodes_added}
    except Exception as e:
        print(f"Ingest Error: {e}")
        if data.url in crawled_sources:
            crawled_sources[data.url]["status"] = "failed"
            _save_crawled_sources_to_disk()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/data")
def get_graph_data(url: Optional[str] = None, depth: int = 1, limit: int = 250, response: Response = None):
    """Returns graph nodes and edges for Knowledge Graph view."""
    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    if not kg.driver:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0, "error": "Neo4j not connected"}

    try:
        url_clean = url.strip() if url else ""

        with kg.driver.session() as s:
            if url_clean and url_clean.lower() != "all":
                nodes_res = s.run("""
                    MATCH (p:Page)
                    WHERE toLower(p.url) CONTAINS toLower($url) OR toLower($url) CONTAINS toLower(p.url)
                    OPTIONAL MATCH (p)-[:MENTIONS]->(mentioned:Entity)
                    OPTIONAL MATCH (a:Entity)-[r]->(b:Entity)
                      WHERE toLower(a.source_url) CONTAINS toLower($url) OR toLower(r.source_url) CONTAINS toLower($url)
                    WITH p,
                         collect(DISTINCT mentioned) AS mentioned_entities,
                         collect(DISTINCT a) + collect(DISTINCT b) AS rel_entities
                    RETURN p.url AS page_url, p.title AS page_title,
                           [x IN mentioned_entities + rel_entities WHERE x IS NOT NULL |
                             {text: x.text, label: coalesce(x.label, 'CONCEPT'), category: coalesce(x.category, 'GENERAL')}
                           ] AS entities
                    LIMIT 1
                """, url=url_clean)

                page_record = nodes_res.single()
                nodes = []
                edges = []
                seen_node_ids = set()

                if page_record and page_record["page_url"]:
                    p_url = page_record["page_url"]
                    clean_topic = _extract_topic_title(p_url, page_record["page_title"] or "")

                    nodes.append({"id": p_url, "label": "PAGE", "text": f"🌟 {clean_topic}", "category": "PAGE"})
                    seen_node_ids.add(p_url)

                    ent_list = page_record["entities"] or []
                    for ent in ent_list:
                        txt = ent.get("text")
                        if txt and txt not in seen_node_ids:
                            seen_node_ids.add(txt)
                            nodes.append({
                                "id": txt,
                                "label": ent.get("label", "CONCEPT"),
                                "text": txt,
                                "category": ent.get("category", "GENERAL")
                            })

                rels_res = s.run("""
                    MATCH (a:Entity)-[r]->(b:Entity)
                    WHERE toLower(a.source_url) CONTAINS toLower($url) OR toLower(r.source_url) CONTAINS toLower($url)
                    RETURN a.text AS source, type(r) AS relation, b.text AS target, properties(r) AS properties
                    LIMIT $limit
                """, url=url_clean, limit=limit)

                for r in rels_res:
                    src, tgt, rel = r["source"], r["target"], r["relation"]
                    if src in seen_node_ids and tgt in seen_node_ids:
                        edges.append({
                            "from": src, "to": tgt, "source": src, "target": tgt,
                            "relation": rel, "properties": r["properties"] or {}
                        })

            else:
                nodes_res = s.run("""
                    MATCH (n:Entity)
                    RETURN
                        id(n) AS neo4j_id,
                        n.text AS text,
                        coalesce(n.label,'CONCEPT') AS label,
                        labels(n) AS labels,
                        coalesce(n.category,'GENERAL') AS category,
                        coalesce(n.source_url,'') AS source
                    LIMIT $limit
                """, limit=limit)
                nodes = [dict(r) for r in nodes_res]

                rels_res = s.run("""
                    MATCH (a:Entity)-[r]->(b:Entity)
                    RETURN a.text AS source, type(r) AS relation, b.text AS target,properties(r) AS properties
                    LIMIT $limit
                """, limit=limit)
                edges = [{"from": r["source"], "to": r["target"], "source": r["source"], "target": r["target"], "relation": r["relation"], "properties": r["properties"]} for r in rels_res]

        return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}
    except Exception as e:
        print(f"[Graph Data Error]: {e}")
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0, "error": str(e)}


@app.get("/graph", response_class=HTMLResponse)
def serve_graph(url: Optional[str] = None):
    """Serves graph.html directly when visiting http://localhost:8000/graph"""
    graph_path = os.path.join(os.getcwd(), "graph.html")
    if os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as f:
            html = f.read()
        mtime = datetime.utcfromtimestamp(os.path.getmtime(graph_path)).isoformat()
        html = f"<!-- served_from: {graph_path} | file_last_modified: {mtime}Z | served_at: {datetime.utcnow().isoformat()}Z -->\n" + html
        return HTMLResponse(
            content=html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return HTMLResponse(content=f"<h2>graph.html not found at {graph_path}</h2>")


@app.get("/chat/history")
def get_chat_history(chat_id: str = "default"):
    return {"chat_id": chat_id, "messages": chat_histories.get(chat_id, [])}


@app.get("/chat/list")
def list_chats():
    chats = []
    for chat_id, messages in chat_histories.items():
        if messages:
            chats.append({
                "chat_id":       chat_id,
                "title":         messages[0]["question"],
                "last_question": messages[-1]["question"],
                "message_count": len(messages)
            })
    return {"chats": chats}


@app.delete("/chat/{chat_id}")
def delete_chat(chat_id: str):
    if chat_id in chat_histories:
        del chat_histories[chat_id]
        _save_chat_histories_to_disk()
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Chat not found")
