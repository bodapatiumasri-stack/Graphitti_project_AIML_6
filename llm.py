import os
import cohere

client = cohere.ClientV2(os.getenv("COHERE_API_KEY"))

def generate_answer(query: str, context: str) -> str:
       
    greetings = ["hi", "hello", "hey", "hii", "helo", "hai"]
    if query.lower().strip().rstrip("!?.") in greetings:
        return "Hello! I am Graphitti, a Graph-Native Web Intelligence Assistant. I can answer medical questions about diseases, symptoms, drugs and treatments. Try asking me something like 'What are symptoms of diabetes?' or 'What drug treats asthma?'"


    if not context.strip():
        return "I don't have enough information to answer this question."

    prompt = f"""You are Graphitti, a helpful medical assistant powered by a knowledge graph built from WebMD.

IMPORTANT RULES:
- Answer the question using the context provided below
- Be helpful even if the question has spelling mistakes or missing question marks or having grammatical errors
- If the user asks about symptoms, causes, treatments or drugs — answer from context
- Keep answer clear and readable
- Do NOT say "I don't have relevant information about it" if there is any related information in the context
- If context has partial information, use it to give a helpful partial answer
- if they say "Hi", respond calmly and introduce yourself and your capabilities
Context from Knowledge Graph and Documents:
{context}

User Question: {query}

Answer helpfully and clearly:"""

    response = client.chat(
        model="command-r-plus-08-2024",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return response.message.content[0].text.strip()
