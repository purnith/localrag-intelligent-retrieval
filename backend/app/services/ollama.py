import httpx

from app.config import get_settings

settings = get_settings()
EMBEDDING_MODEL = "nomic-embed-text"


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/embed",
            json={"model": EMBEDDING_MODEL, "input": texts},
        )
        response.raise_for_status()
        return response.json()["embeddings"]


async def generate_grounded_answer(question: str, contexts: list[str]) -> str:
    context_text = "\n\n".join(
        f"Source {index + 1}: {content}" for index, content in enumerate(contexts)
    )
    prompt = f"""Answer the question directly and concisely using only the sources below.
If the sources do not contain the answer, say that the uploaded documents do not provide enough information.
Refer to supporting sources as [Source 1], [Source 2], and so on.
Do not discuss information the question did not ask for, and do not claim a detail is missing if it appears in a source.

{context_text}

Question: {question}
"""
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
