import os
from datetime import datetime
from neo4j import GraphDatabase

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


class KGBuilder:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._setup()

    def _setup(self):
        with self.driver.session() as s:
            s.run("CREATE INDEX page_url IF NOT EXISTS FOR (p:Page) ON (p.url)")
            s.run("CREATE INDEX entity_text IF NOT EXISTS FOR (e:Entity) ON (e.text)")

    def build_or_update(self, url, entities, relationships, raw_text, page_title=""):
        ts = datetime.utcnow().isoformat()
        nodes_added = 0
        rels_added  = 0

        with self.driver.session() as s:
            s.run("""
                MERGE (p:Page {url: $url})
                SET p.title = $title, p.last_crawled = $ts, p.snippet = $snippet
            """, url=url, title=page_title, ts=ts, snippet=raw_text[:400])

            for ent in entities:
                r = s.run("""
                    MERGE (e:Entity {text: $text, label: $label})
                    ON CREATE SET e.created_at = $ts
                    WITH e
                    MATCH (p:Page {url: $url})
                    MERGE (p)-[:MENTIONS]->(e)
                    RETURN e
                """, text=ent["text"], label=ent["label"], ts=ts, url=url)
                nodes_added += r.consume().counters.nodes_created

            for rel in relationships:
                r = s.run("""
                    MERGE (a:Entity {text: $src})
                    MERGE (b:Entity {text: $tgt})
                    MERGE (a)-[r:RELATION {type: $rel_type}]->(b)
                    ON CREATE SET r.source_url = $url, r.created_at = $ts
                    RETURN r
                """, src=rel["source"], tgt=rel["target"],
                     rel_type=rel["relation"], url=url, ts=ts)
                rels_added += r.consume().counters.relationships_created

        return {"nodes_added": nodes_added, "relationships_added": rels_added}

    def graph_search_all(self, query: str) -> dict:
        keywords = self._keywords_from_query(query)
        if not keywords:
            return {"nodes": [], "triples": [], "context_text": "", "sources": []}

        pattern = "(?i).*(" + "|".join(keywords) + ").*"

        with self.driver.session() as s:
            seed_entities = [r["text"] for r in s.run("""
                MATCH (e:Entity)
                WHERE e.text =~ $pattern
                RETURN e.text AS text
                LIMIT 10
            """, pattern=pattern)]

            if not seed_entities:
                return {"nodes": [], "triples": [], "context_text": "", "sources": []}

            outward = [dict(r) for r in s.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE a.text IN $seeds
                RETURN a.text AS src, r.type AS rel, b.text AS tgt, r.source_url AS url
                LIMIT 30
            """, seeds=seed_entities)]

            inward = [dict(r) for r in s.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE b.text IN $seeds
                RETURN a.text AS src, r.type AS rel, b.text AS tgt, r.source_url AS url
                LIMIT 30
            """, seeds=seed_entities)]

        triples = []
        nodes   = set(seed_entities)
        sources = set()

        for rec in outward + inward:
            triple = f"{rec['src']} --[{rec['rel']}]--> {rec['tgt']}"
            triples.append(triple)
            nodes.add(rec["src"])
            nodes.add(rec["tgt"])
            if rec["url"]:
                sources.add(rec["url"])

        context_text = "\n".join(triples) if triples else ", ".join(seed_entities)

        return {
            "nodes":        list(nodes),
            "triples":      triples,
            "context_text": context_text,
            "sources":      list(sources),
        }

    def _keywords_from_query(self, query: str) -> list[str]:
        stopwords = {
            "what", "is", "are", "the", "a", "an", "of", "for", "to",
            "how", "does", "do", "and", "or", "in", "on", "at", "with",
            "about", "tell", "me", "explain", "describe", "give", "list",
            "which", "who", "when", "why", "can", "used", "treat", "treats"
        }
        words = query.lower().split()
        return [w.strip("?.,!") for w in words if w not in stopwords and len(w) > 2]

    def kg_exists(self, url: str) -> bool:
        with self.driver.session() as s:
            result = s.run("MATCH (p:Page {url: $url}) RETURN p LIMIT 1", url=url)
            return result.single() is not None

    def get_stats(self, url: str) -> dict:
        with self.driver.session() as s:
            nodes = s.run("""
                MATCH (p:Page {url: $url})-[:MENTIONS]->(e:Entity)
                RETURN count(e) AS cnt
            """, url=url).single()["cnt"]
            rels = s.run("""
                MATCH (p:Page {url: $url})-[:MENTIONS]->(a:Entity)-[:RELATION]->(:Entity)
                RETURN count(*) AS cnt
            """, url=url).single()["cnt"]
        return {"nodes": nodes, "relationships": rels}