import json

from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_pool
from app.schemas import UserCreate

router = APIRouter(prefix="/api", tags=["context"])


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(request: UserCreate) -> dict[str, object]:
    display_name = request.display_name.strip()
    if not display_name:
        raise HTTPException(422, "Display name cannot be empty")
    row = await get_pool().fetchrow(
        "INSERT INTO users(display_name) VALUES($1) RETURNING id, display_name, created_at",
        display_name,
    )
    return dict(row)


@router.get("/users/{user_id}")
async def get_user(user_id: int) -> dict[str, object]:
    row = await get_pool().fetchrow(
        "SELECT id, display_name, created_at FROM users WHERE id = $1", user_id
    )
    if row is None:
        raise HTTPException(404, "User not found")
    return dict(row)


@router.get("/conversations")
async def list_conversations(user_id: int = Query(gt=0)) -> list[dict[str, object]]:
    rows = await get_pool().fetch(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id)::int AS messages
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        WHERE c.user_id = $1
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        """,
        user_id,
    )
    return [dict(row) for row in rows]


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: int, user_id: int = Query(gt=0)
) -> list[dict[str, object]]:
    exists = await get_pool().fetchval(
        "SELECT EXISTS(SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2)",
        conversation_id,
        user_id,
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
async def delete_conversation(conversation_id: int, user_id: int = Query(gt=0)) -> None:
    result = await get_pool().execute(
        "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id,
        user_id,
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Conversation not found")
