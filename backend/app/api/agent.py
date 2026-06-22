from fastapi import APIRouter, HTTPException

from app.api.retrieval import search_chunks
from app.database import get_pool
from app.schemas import AgentResponse, QueryRequest, SearchResult
from app.services.agent import choose_agent_action
from app.services.memory import get_or_create_conversation, load_recent_history, save_message
from app.services.ollama import (
    generate_document_summary,
    generate_grounded_answer,
    generate_memory_answer,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


async def load_summary_sources(
    user_id: int, document_ids: list[int] | None
) -> list[SearchResult]:
    rows = await get_pool().fetch(
        """
        SELECT c.id AS chunk_id, d.id AS document_id, d.filename, c.content,
               1.0::double precision AS score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.user_id = $1
          AND ($2::bigint[] IS NULL OR d.id = ANY($2::bigint[]))
        ORDER BY d.id, c.chunk_index
        LIMIT 30
        """,
        user_id,
        document_ids or None,
    )
    return [SearchResult(**dict(row)) for row in rows]


@router.post("/ask", response_model=AgentResponse)
async def agent_ask(request: QueryRequest) -> AgentResponse:
    conversation_id = await get_or_create_conversation(
        request.user_id, request.conversation_id, request.query
    )
    history = await load_recent_history(conversation_id)
    decision = await choose_agent_action(request.query, history)
    await save_message(conversation_id, "user", request.query)
    trace = [f"planner:selected:{decision.action}"]
    sources: list[SearchResult] = []

    try:
        if decision.action == "clarify":
            answer = decision.clarification or "Could you clarify what you want me to do?"
            trace.append("clarification:requested")
        elif decision.action == "conversation_memory":
            trace.append("conversation_memory:read")
            answer = (
                await generate_memory_answer(request.query, history)
                if history
                else "There is no earlier conversation context yet. Please provide more detail."
            )
        elif decision.action == "summarize_documents":
            trace.append("document_store:loaded")
            sources = await load_summary_sources(request.user_id, request.document_ids)
            answer = (
                await generate_document_summary(
                    decision.tool_input, [source.content for source in sources]
                )
                if sources
                else "No documents are available to summarize."
            )
        else:
            trace.append("hybrid_retrieval:executed")
            sources = await search_chunks(
                decision.tool_input,
                request.limit,
                request.user_id,
                request.document_ids,
            )
            answer = (
                await generate_grounded_answer(
                    request.query, [source.content for source in sources], history
                )
                if sources
                else "The selected documents do not contain enough relevant information to answer that question."
            )
    except Exception as error:
        raise HTTPException(503, "The agent could not complete the selected tool") from error

    trace.append("response:persisted")
    await save_message(conversation_id, "assistant", answer, sources)
    return AgentResponse(
        answer=answer,
        sources=sources,
        conversation_id=conversation_id,
        action=decision.action,
        tool_trace=trace,
    )
