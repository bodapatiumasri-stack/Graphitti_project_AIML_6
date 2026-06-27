import os
import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


class RetrievalEngine:
    def __init__(self, kg):
        self.kg = kg
        self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.chroma.get_or_create_collection(
            name="graphitti_docs",
            metadata={"hnsw:space": "cosine"}
        )
        self.embedder = SentenceTransformer(EMBED_MODEL)

    def index(self, url: str, text: str, title: str = ""):
        chunks = self._chunk(text)
        if not chunks:
            return
        embeddings = self.embedder.encode(chunks).tolist()
        ids        = [f"{url}::chunk::{i}" for i in range(len(chunks))]
        metadatas  = [{"url": url, "title": title, "chunk": i} for i in range(len(chunks))]
        self.collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def retrieve_all(self, query: str, top_k: int = 5):
        vector_chunks, vector_sources = self._vector_search_all(query, top_k)
        graph_result = self.kg.graph_search_all(query)

        context_parts = []
        if graph_result["context_text"]:
            context_parts.append(
                "=== Knowledge Graph (Entity Relationships) ===\n"
                + graph_result["context_text"]
            )
        if vector_chunks:
            context_parts.append(
                "=== Relevant Document Passages ===\n"
                + "\n\n".join(vector_chunks)
            )

        context = "\n\n".join(context_parts) if context_parts else ""
        sources = list(set(vector_sources + graph_result.get("sources", [])))
        return context, sources, graph_result["nodes"]

    def _vector_search_all(self, query: str, top_k: int):
        query_embedding = self.embedder.encode([query])[0].tolist()
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )
            chunks  = results["documents"][0] if results["documents"] else []
            sources = [m["url"] for m in results["metadatas"][0]] if results["metadatas"] else []
            return chunks, sources
        except Exception:
            return [], []

    def _chunk(self, text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
        words  = text.split()
        chunks = []
        start  = 0
        while start < len(words):
            chunks.append(" ".join(words[start: start + chunk_size]))
            start += chunk_size - overlap
        return chunks
