from fastapi import APIRouter, HTTPException

from app.database import get_pool
from app.schemas import AskResponse, QueryRequest, SearchResult
from app.services.ollama import create_embeddings, generate_grounded_answer

router = APIRouter(prefix="/api", tags=["retrieval"])


async def search_chunks(query: str, limit: int) -> list[SearchResult]:
    try:
        query_embedding = (await create_embeddings([query]))[0]
    except Exception as error:
        raise HTTPException(503, "The local embedding model is unavailable") from error

    rows = await get_pool().fetch(
        """
        SELECT c.id AS chunk_id, d.id AS document_id, d.filename, c.content,
               1 - (c.embedding <=> $1::vector) AS score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> $1::vector
        LIMIT $2
        """,
        str(query_embedding),
        limit,
    )
    return [SearchResult(**dict(row)) for row in rows]


@router.post("/search", response_model=list[SearchResult])
async def semantic_search(request: QueryRequest) -> list[SearchResult]:
    return await search_chunks(request.query, request.limit)


@router.post("/ask", response_model=AskResponse)
async def ask_documents(request: QueryRequest) -> AskResponse:
    sources = await search_chunks(request.query, request.limit)
    if not sources:
        return AskResponse(
            answer="Upload at least one document before asking a question.", sources=[]
        )
    try:
        answer = await generate_grounded_answer(
            request.query, [source.content for source in sources]
        )
    except Exception as error:
        raise HTTPException(503, "The local language model is unavailable") from error
    return AskResponse(answer=answer, sources=sources)
