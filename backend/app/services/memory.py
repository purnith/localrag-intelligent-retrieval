import json

from fastapi import HTTPException

from app.database import get_pool
from app.schemas import SearchResult


def build_contextual_query(
    query: str, history: list[dict[str, str]], max_user_messages: int = 2
) -> str:
    recent_user_messages = [
        message["content"] for message in history if message["role"] == "user"
    ][-max_user_messages:]
    return " ".join([*recent_user_messages, query])


def conversation_title(query: str, max_length: int = 80) -> str:
    return " ".join(query.split())[:max_length]


async def get_or_create_conversation(
    user_id: int, conversation_id: int | None, query: str
) -> int:
    database = get_pool()
    user_exists = await database.fetchval(
        "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)", user_id
    )
    if not user_exists:
        raise HTTPException(404, "User not found")
    if conversation_id is None:
        return await database.fetchval(
            "INSERT INTO conversations(user_id, title) VALUES($1, $2) RETURNING id",
            user_id,
            conversation_title(query),
        )
    belongs_to_user = await database.fetchval(
        "SELECT EXISTS(SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2)",
        conversation_id,
        user_id,
    )
    if not belongs_to_user:
        raise HTTPException(404, "Conversation not found")
    return conversation_id


async def load_recent_history(
    conversation_id: int, limit: int = 8
) -> list[dict[str, str]]:
    rows = await get_pool().fetch(
        """
        SELECT role, content FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at DESC LIMIT $2
        """,
        conversation_id,
        limit,
    )
    return [dict(row) for row in reversed(rows)]


async def save_message(
    conversation_id: int,
    role: str,
    content: str,
    sources: list[SearchResult] | None = None,
) -> None:
    serialized_sources = None
    if sources is not None:
        serialized_sources = json.dumps([source.model_dump() for source in sources])
    await get_pool().execute(
        """
        INSERT INTO messages(conversation_id, role, content, sources)
        VALUES($1, $2, $3, $4::jsonb)
        """,
        conversation_id,
        role,
        content,
        serialized_sources,
    )
    await get_pool().execute(
        "UPDATE conversations SET updated_at = NOW() WHERE id = $1", conversation_id
    )
