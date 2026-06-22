import json
from typing import Literal

from pydantic import BaseModel, Field

AgentAction = Literal[
    "search_documents", "summarize_documents", "conversation_memory", "clarify"
]


class AgentDecision(BaseModel):
    action: AgentAction
    tool_input: str = Field(min_length=1, max_length=2000)
    clarification: str | None = Field(default=None, max_length=500)


def fallback_decision(query: str) -> AgentDecision:
    normalized = query.lower()
    if any(word in normalized for word in ("summarize", "summary", "overview")):
        action: AgentAction = "summarize_documents"
    elif any(
        phrase in normalized
        for phrase in ("what did i ask", "previous answer", "our conversation")
    ):
        action = "conversation_memory"
    else:
        action = "search_documents"
    return AgentDecision(action=action, tool_input=query)


def parse_agent_decision(content: str, query: str) -> AgentDecision:
    try:
        return AgentDecision.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError, TypeError):
        return fallback_decision(query)


async def choose_agent_action(
    query: str, history: list[dict[str, str]]
) -> AgentDecision:
    from app.services.ollama import chat

    history_text = "\n".join(
        f"{message['role']}: {message['content']}" for message in history[-6:]
    )
    prompt = f"""Select exactly one tool for the user's request.

Tools:
- search_documents: factual questions, comparisons, and evidence lookup in uploaded documents
- summarize_documents: explicit requests to summarize or provide an overview of documents
- conversation_memory: questions explicitly about prior messages or answers
- clarify: requests that are too ambiguous to select a useful tool

Rewrite tool_input as a standalone request when the user refers to earlier context.
For clarify, provide one concise clarification question.
Return JSON only with: action, tool_input, clarification.

Conversation:
{history_text or 'No prior conversation.'}

User request: {query}
"""
    try:
        content = await chat([{"role": "user", "content": prompt}], json_format=True)
        return parse_agent_decision(content, query)
    except Exception:
        return fallback_decision(query)
