import os
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import chromadb
from rank_bm25 import BM25Okapi

class RetrievalEngine:
    def __init__(self, kg_builder):
        self.kg = kg_builder
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(name="medical_docs")
    
        self.doc_texts: List[str] = []
        self.doc_sources: List[str] = []
        self.bm25: BM25Okapi = None

    def index(self, url: str, text: str, title: str = ""):
        if not text:
            return

        doc_id = url.replace("https://", "").replace("http://", "").replace("/", "_")
        embedding = self.encoder.encode(text[:1000]).tolist()
        self.collection.upsert(
            documents=[text[:1500]],
            embeddings=[embedding],
            metadatas=[{"url": url, "title": title}],
            ids=[doc_id]
        )

        self.doc_texts.append(text[:1500])
        self.doc_sources.append(url)
    
        tokenized_corpus = [doc.lower().split() for doc in self.doc_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)
        print(f" Ready: Indexed {len(self.doc_texts)} document(s) in BM25 lexical search index!")

    def hybrid_search(self, query: str, top_k: int = 4) -> Dict:
        context_parts = []
        sources = []
        graph_nodes = []

        if self.kg.driver:
            try:
                with self.kg.driver.session() as s:
                    res = s.run("""
                        MATCH (a:Entity)-[r]->(b:Entity)
                        WHERE toLower(a.text) CONTAINS toLower($q) OR toLower(b.text) CONTAINS toLower($q)
                        RETURN a.text AS src, type(r) AS rel, b.text AS tgt, a.source_url AS url
                        LIMIT 10
                    """, q=query[:40])
                    for record in res:
                        src, rel, tgt, url = record["src"], record["rel"], record["tgt"], record["url"]
                        context_parts.append(f"Knowledge Graph Fact: ({src}) -[{rel}]-> ({tgt})")
                        graph_nodes.extend([src, tgt])
                        if url and url not in sources:
                            sources.append(url)
            except Exception as e:
                print(f"Graph retrieval warning: {e}")

        try:
            q_emb = self.encoder.encode(query).tolist()
            vec_res = self.collection.query(query_embeddings=[q_emb], n_results=top_k)
            if vec_res and vec_res.get("documents"):
                for docs, metas in zip(vec_res["documents"], vec_res["metadatas"]):
                    for doc, meta in zip(docs, metas):
                        context_parts.append(f"Vector Context: {doc}")
                        if meta.get("url") and meta["url"] not in sources:
                            sources.append(meta["url"])
        except Exception as vec_err:
            print(f"Vector search warning: {vec_err}")

        if self.bm25 and self.doc_texts:
            try:
                tokenized_query = query.lower().split()
                bm25_scores = self.bm25.get_scores(tokenized_query)
                top_idx = max(range(len(bm25_scores)), key=lambda i: bm25_scores[i])
                
                if bm25_scores[top_idx] > 0.05:
                    bm25_snippet = self.doc_texts[top_idx][:400]
                    bm25_url = self.doc_sources[top_idx]
                    context_parts.append(f"BM25 Keyword Fact: {bm25_snippet}")
                    if bm25_url not in sources:
                        sources.append(bm25_url)
            except Exception as bm25_err:
                print(f"BM25 search warning: {bm25_err}")

        return {
            "context": "\n".join(context_parts),
            "sources": sources,
            "graph_nodes": list(set(graph_nodes))
        }
