from fastapi import APIRouter, HTTPException

from app.api.auth import CurrentUser
from app.database import get_pool
from app.schemas import AskResponse, QueryRequest, SearchResult
from app.services.cache import (
    get_cached_search_results,
    retrieval_cache_key,
    set_cached_search_results,
)
from app.services.memory import (
    build_contextual_query,
    get_or_create_conversation,
    load_recent_history,
    save_message,
)
from app.services.ollama import create_embeddings, generate_grounded_answer

router = APIRouter(prefix="/api", tags=["retrieval"])


async def search_chunks(
    query: str, limit: int, user_id: int, document_ids: list[int] | None = None
) -> list[SearchResult]:
    cache_key = retrieval_cache_key(query, limit, user_id, document_ids)
    cached_results = await get_cached_search_results(cache_key)
    if cached_results is not None:
        return cached_results

    try:
        query_embedding = (await create_embeddings([query]))[0]
    except Exception as error:
        raise HTTPException(503, "The local embedding model is unavailable") from error

    rows = await get_pool().fetch(
        """
        WITH scored AS (
            SELECT c.id AS chunk_id, d.id AS document_id, d.filename, c.content,
                   1 - (c.embedding <=> $1::vector) AS vector_score,
                   CASE
                       WHEN to_tsvector('english', c.content)
                            @@ plainto_tsquery('english', $2)
                       THEN 1.0
                       ELSE 0.0
                   END AS keyword_score
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.user_id = $3
              AND ($4::bigint[] IS NULL OR d.id = ANY($4::bigint[]))
        ),
        deduplicated AS (
            SELECT DISTINCT ON (md5(content))
                   chunk_id, document_id, filename, content,
                   (0.8 * vector_score + 0.2 * keyword_score) AS score
            FROM scored
            ORDER BY md5(content),
                     (0.8 * vector_score + 0.2 * keyword_score) DESC
        )
        SELECT chunk_id, document_id, filename, content, score
        FROM deduplicated
        ORDER BY score DESC
        LIMIT $5
        """,
        str(query_embedding),
        query,
        user_id,
        document_ids or None,
        limit,
    )
    results = [SearchResult(**dict(row)) for row in rows]
    await set_cached_search_results(cache_key, results)
    return results


@router.post("/search", response_model=list[SearchResult])
async def semantic_search(
    request: QueryRequest, current_user: CurrentUser
) -> list[SearchResult]:
    return await search_chunks(
        request.query, request.limit, current_user.id, request.document_ids
    )


@router.post("/ask", response_model=AskResponse)
async def ask_documents(
    request: QueryRequest, current_user: CurrentUser
) -> AskResponse:
    conversation_id = await get_or_create_conversation(
        current_user.id, request.conversation_id, request.query
    )
    history = await load_recent_history(conversation_id)
    await save_message(conversation_id, "user", request.query)

    retrieval_query = build_contextual_query(request.query, history)
    sources = await search_chunks(
        retrieval_query, request.limit, current_user.id, request.document_ids
    )
    if not sources:
        answer = "The selected documents do not contain enough relevant information to answer that question."
        await save_message(conversation_id, "assistant", answer, [])
        return AskResponse(answer=answer, sources=[], conversation_id=conversation_id)
    try:
        answer = await generate_grounded_answer(
            request.query, [source.content for source in sources], history
        )
    except Exception as error:
        raise HTTPException(503, "The local language model is unavailable") from error
    await save_message(conversation_id, "assistant", answer, sources)
    return AskResponse(
        answer=answer, sources=sources, conversation_id=conversation_id
    )
