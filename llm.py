import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def generate_answer(query: str, context: str, chat_history: list = None) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "GROQ_API_KEY is not set in .env. Please add it to generate LLM answers."

    client = Groq(api_key=api_key)
    trimmed_context = context[:2500].strip() if context else "No context available."
    system_prompt = (
    "You are Graphitti, an intelligent medical AI assistant powered by a Knowledge Graph.\n"
    "Answer accurately based on the Knowledge Context provided below.\n\n"
    "STRICT RULES:\n"
    "1. Do NOT use asterisks or stars like ** or * anywhere in your response\n"
    "2. Do NOT bold any text\n"
    "3. Use numbered points like 1. 2. 3. for lists\n"
    "4. Write in plain text only\n"
    "5. Give answer in English only\n"
    "6. Be concise and easy to read\n\n"
    "7.Use side headings if possible to organize the answer\n"
    "8. Keep the answer concise but informative, focusing on the most relevant information\n"
    f"KNOWLEDGE CONTEXT:\n{trimmed_context}"
     )  
    messages = [{"role": "system", "content": system_prompt}]
    
    if chat_history:
        messages.extend(chat_history[-4:])

    user_content = f"Context:\n{context}\n\nUser Question: {query}"
    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"LLM Error: {str(e)}"
