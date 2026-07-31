from typing import Dict, List

class IntentRouterAgent:
    
    @staticmethod
    def analyze_intent(question: str) -> Dict[str, str]:
        q_lower = question.lower().strip()
        
        if q_lower in ["hi", "hello", "hey", "greetings", "hii", "helo"]:
            return {"intent": "greeting", "complexity": "low"}
            
        multi_hop_keywords = ["relationship between", "how does", "connected to", "causes of symptoms", "drug for condition", "interact with"]
        if any(kw in q_lower for kw in multi_hop_keywords):
            return {"intent": "multi_hop_graph", "complexity": "high"}

        medical_keywords = ["symptom", "treatment", "cause", "drug", "medicine", "cure", "disease", "side effect", "organ"]
        if any(kw in q_lower for kw in medical_keywords):
            return {"intent": "medical_fact", "complexity": "medium"}

        return {"intent": "general_retrieval", "complexity": "medium"}


class ContextSynthesizerAgent:
    
    @staticmethod
    def synthesize(raw_results: Dict) -> Dict:
        context_str = raw_results.get("context", "")
        lines = [line.strip() for line in context_str.splitlines() if line.strip()]
        
        unique_lines = []
        seen = set()
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
                
        synthesized_context = "\n".join(unique_lines[:8])
        
        return {
            "context": synthesized_context,
            "sources": list(set(raw_results.get("sources", []))),
            "graph_nodes": list(set(raw_results.get("graph_nodes", [])))
        }


class OrchestratorAgent:
    
    def __init__(self, retrieval_engine):
        self.retrieval = retrieval_engine
        self.router = IntentRouterAgent()
        self.synthesizer = ContextSynthesizerAgent()

    def run(self, question: str) -> Dict:
        # 1. Intent Routing
        intent_info = self.router.analyze_intent(question)
        intent_type = intent_info["intent"]
        
        if intent_type == "greeting":
            return {
                "context": "",
                "sources": [],
                "graph_nodes": [],
                "strategy": "greeting_handler",
                "intent": "greeting"
            }

        # 2. Select & Execute Strategy
        if intent_type == "multi_hop_graph":
            strategy_name = "multi_hop_graph_traversal"
            raw_results = self.retrieval.hybrid_search(question, top_k=6)
        elif intent_type == "medical_fact":
            strategy_name = "tri_hybrid_rag_search"
            raw_results = self.retrieval.hybrid_search(question, top_k=4)
        else:
            strategy_name = "dense_semantic_search"
            raw_results = self.retrieval.hybrid_search(question, top_k=3)

        # 3. Context Synthesis
        final_result = self.synthesizer.synthesize(raw_results)
        final_result["strategy"] = strategy_name
        final_result["intent"] = intent_type
        
        return final_result
