import os
import cohere

client = cohere.ClientV2(os.getenv("COHERE_API_KEY"))

def generate_answer(query: str, context: str) -> str:
    if not context.strip():
        return "No relevant information found."

    response = client.chat(
        model="command-r-plus-08-2024",
        messages=[
            {
                "role": "system",
                "content": "You are Graphitti, a medical web intelligence assistant. Answer using ONLY the provided context. If answer is not in context say I don't know."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}"
            }
        ]
    )
    return response.message.content[0].text.strip()