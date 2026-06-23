import httpx

from app.config import get_settings

settings = get_settings()
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_BATCH_SIZE = 32


async def chat(
    messages: list[dict[str, str]], json_format: bool = False
) -> str:
    payload: dict[str, object] = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0},
    }
    if json_format:
        payload["format"] = "json"
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty response")
        return content.strip()


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=180) as client:
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            response = await client.post(
                f"{settings.ollama_url}/api/embed",
                json={
                    "model": EMBEDDING_MODEL,
                    "input": texts[start : start + EMBEDDING_BATCH_SIZE],
                },
            )
            response.raise_for_status()
            embeddings.extend(response.json()["embeddings"])
    return embeddings


async def generate_grounded_answer(
    question: str, contexts: list[str], history: list[dict[str, str]] | None = None
) -> str:
    context_text = "\n\n".join(
        f"Source {index + 1}: {content}" for index, content in enumerate(contexts)
    )
    history_text = "\n".join(
        f"{message['role'].title()}: {message['content']}"
        for message in (history or [])
    )
    prompt = f"""Answer the question directly and concisely using only the sources below.
If the sources do not contain the answer, say that the uploaded documents do not provide enough information.
Refer to supporting sources as [Source 1], [Source 2], and so on.
Do not discuss information the question did not ask for, and do not claim a detail is missing if it appears in a source.
Use the conversation history only to understand references in the current question. Do not treat conversation history as factual source evidence.

Conversation history:
{history_text or 'No previous messages.'}

{context_text}

Question: {question}
"""
    return await chat([{"role": "user", "content": prompt}])


async def generate_document_summary(
    question: str, contexts: list[str]
) -> str:
    document_text = "\n\n".join(
        f"Passage {index + 1}: {content}" for index, content in enumerate(contexts)
    )
    return await chat(
        [
            {
                "role": "system",
                "content": "Summarize only the supplied document passages. Preserve important facts and state when the available passages are insufficient.",
            },
            {
                "role": "user",
                "content": f"Request: {question}\n\n{document_text}",
            },
        ]
    )


async def generate_document_analysis(question: str, contexts: list[str]) -> str:
    document_text = "\n\n".join(
        f"Passage {index + 1}: {content}" for index, content in enumerate(contexts)
    )
    return await chat(
        [
            {
                "role": "system",
                "content": "Analyze only the supplied document passages. Identify strengths, weaknesses, inconsistencies, and specific improvements. Support observations with the document content and do not invent missing details.",
            },
            {
                "role": "user",
                "content": f"Review request: {question}\n\n{document_text}",
            },
        ]
    )


async def generate_memory_answer(
    question: str, history: list[dict[str, str]]
) -> str:
    history_text = "\n".join(
        f"{message['role'].title()}: {message['content']}" for message in history
    )
    return await chat(
        [
            {
                "role": "system",
                "content": "Answer only from the supplied conversation history. If it does not contain the answer, ask the user to clarify or search their documents.",
            },
            {
                "role": "user",
                "content": f"Conversation history:\n{history_text}\n\nCurrent question: {question}",
            },
        ]
    )
