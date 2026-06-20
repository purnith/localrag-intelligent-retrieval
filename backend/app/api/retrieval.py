from fastapi import APIRouter, HTTPException

from app.database import get_pool
from app.schemas import AskResponse, QueryRequest, SearchResult
from app.services.ollama import create_embeddings, generate_grounded_answer

router = APIRouter(prefix="/api", tags=["retrieval"])
MIN_VECTOR_SIMILARITY = 0.5


async def search_chunks(
    query: str, limit: int, document_ids: list[int] | None = None
) -> list[SearchResult]:
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
            WHERE ($3::bigint[] IS NULL OR d.id = ANY($3::bigint[]))
        ),
        deduplicated AS (
            SELECT DISTINCT ON (md5(content))
                   chunk_id, document_id, filename, content,
                   (0.8 * vector_score + 0.2 * keyword_score) AS score
            FROM scored
            WHERE vector_score >= $4
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
        document_ids or None,
        MIN_VECTOR_SIMILARITY,
        limit,
    )
    return [SearchResult(**dict(row)) for row in rows]


@router.post("/search", response_model=list[SearchResult])
async def semantic_search(request: QueryRequest) -> list[SearchResult]:
    return await search_chunks(request.query, request.limit, request.document_ids)


@router.post("/ask", response_model=AskResponse)
async def ask_documents(request: QueryRequest) -> AskResponse:
    sources = await search_chunks(request.query, request.limit, request.document_ids)
    if not sources:
        return AskResponse(
            answer="The selected documents do not contain enough relevant information to answer that question.",
            sources=[],
        )
    try:
        answer = await generate_grounded_answer(
            request.query, [source.content for source in sources]
        )
    except Exception as error:
        raise HTTPException(503, "The local language model is unavailable") from error
    return AskResponse(answer=answer, sources=sources)
