import os
from neo4j import GraphDatabase

class KGBuilder:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.verify_connection()
            print(" Neo4j connected successfully!")
        except Exception as e:
            print(f"⚠️ Neo4j connection error: {e}")
            self.driver = None

    def verify_connection(self) -> bool:
        if not self.driver: return False
        try:
            with self.driver.session() as s:
                return s.run("RETURN 1 AS test").single()["test"] == 1
        except Exception: return False

    def close(self):
        if self.driver: self.driver.close()

    def get_all_stats(self) -> dict:
        if not self.driver: return {"nodes": 0, "relationships": 0}
        try:
            with self.driver.session() as s:
                n = s.run("MATCH (n) RETURN count(n) AS count").single()["count"]
                r = s.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
                return {"nodes": n, "relationships": r}
        except Exception: return {"nodes": 0, "relationships": 0}

    def build_or_update(self, url: str, entities: list, relationships: list, raw_text: str, page_title: str = ""):
        if not self.driver:
            raise Exception("Neo4j driver is not connected.")
            
        with self.driver.session() as session:
            # 1. Create Page Root Node
            title_val = page_title or url.replace("https://", "").replace("http://", "").split("/")[0]
            session.run("""
                MERGE (p:Page {url: $url})
                ON CREATE SET p.title = $title, p.created_at = timestamp()
                ON MATCH SET p.title = $title
            """, url=url, title=title_val)

            # 2. Ingest Entities and Link to Page Node (:Page)-[:MENTIONS]->(:Entity)
            for ent in entities:
                text_val = ent.get("text") or ent.get("name")
                label_val = (ent.get("label") or ent.get("type") or "CONCEPT").upper().replace(" ", "_")
                
                if text_val and len(text_val) > 1:
                    session.run("""
                        MERGE (e:Entity {text: $text})
                        ON CREATE SET e.label = $label, e.source_url = $url, e.created_at = timestamp()
                        ON MATCH SET e.label = coalesce($label, e.label), e.source_url = $url
                        WITH e
                        MATCH (p:Page {url: $url})
                        MERGE (p)-[:MENTIONS]->(e)
                    """, text=text_val, label=label_val, url=url)
            
            # 3. Ingest Entity-to-Entity Dynamic Relationships
            for rel in relationships:
                src = rel.get("source")
                tgt = rel.get("target")
                rel_type = (rel.get("relation") or rel.get("type") or "ASSOCIATED_WITH").upper().replace(" ", "_")
                
                if src and tgt and src != tgt:
                    query = f"""
                        MATCH (a:Entity {{text: $src}})
                        MATCH (b:Entity {{text: $tgt}})
                        MERGE (a)-[r:{rel_type}]->(b)
                        ON CREATE SET r.source_url = $url, r.type = $rel_type
                    """
                    session.run(query, src=src, tgt=tgt, url=url, rel_type=rel_type)

        return {"nodes_added": len(entities) + 1}
