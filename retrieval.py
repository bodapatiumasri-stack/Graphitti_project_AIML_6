import os
from kg_builder import KGBuilder

class RetrievalEngine:
    def __init__(self, kg: KGBuilder):
        self.kg = kg

    def index(self, url: str, text: str, title: str = ""):
        pass

    def retrieve_all(self, query: str, top_k: int = 5):
        # Only graph retrieval — fast and reliable
        graph_result = self.kg.graph_search_all(query)

        context = ""
        if graph_result["context_text"]:
            context = "=== Knowledge Graph ===\n" + graph_result["context_text"]

        sources = graph_result.get("sources", [])
        nodes   = graph_result.get("nodes", [])

        return context, sources, nodes
