import json

from fastapi import APIRouter, HTTPException, status

from app.api.auth import CurrentUser
from app.database import get_pool

router = APIRouter(prefix="/api", tags=["context"])


@router.get("/conversations")
async def list_conversations(current_user: CurrentUser) -> list[dict[str, object]]:
    rows = await get_pool().fetch(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id)::int AS messages
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        WHERE c.user_id = $1
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        """,
        current_user.id,
    )
    return [dict(row) for row in rows]


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: int, current_user: CurrentUser
) -> list[dict[str, object]]:
    exists = await get_pool().fetchval(
        "SELECT EXISTS(SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2)",
        conversation_id,
        current_user.id,
    )
    if not exists:
        raise HTTPException(404, "Conversation not found")
    rows = await get_pool().fetch(
        """
        SELECT id, role, content, sources, created_at
        FROM messages WHERE conversation_id = $1 ORDER BY created_at
        """,
        conversation_id,
    )
    messages = []
    for row in rows:
        message = dict(row)
        if isinstance(message["sources"], str):
            message["sources"] = json.loads(message["sources"])
        messages.append(message)
    return messages


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int, current_user: CurrentUser
) -> None:
    result = await get_pool().execute(
        "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id,
        current_user.id,
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Conversation not found")
