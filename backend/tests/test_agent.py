import asyncio

from app.services.agent import choose_agent_action, fallback_decision, parse_agent_decision


def test_agent_routes_summary_requests() -> None:
    decision = fallback_decision("Summarize the selected policy documents")
    assert decision.action == "summarize_documents"


def test_agent_routes_generic_document_overview_to_summary() -> None:
    decision = fallback_decision("What is this doc?")
    assert decision.action == "summarize_documents"


def test_agent_routes_natural_document_overview_variation() -> None:
    decision = fallback_decision("What it is doc?")
    assert decision.action == "summarize_documents"


def test_agent_routes_document_review_to_analysis() -> None:
    decision = fallback_decision("Can you review the doc?")
    assert decision.action == "analyze_documents"


def test_agent_routes_conversation_questions_to_memory() -> None:
    decision = fallback_decision("What did I ask in our conversation?")
    assert decision.action == "conversation_memory"


def test_agent_parses_structured_planner_output() -> None:
    decision = parse_agent_decision(
        '{"action":"search_documents","tool_input":"vacation eligibility","clarification":null}',
        "What about eligibility?",
    )
    assert decision.action == "search_documents"
    assert decision.tool_input == "vacation eligibility"


def test_agent_falls_back_safely_on_invalid_output() -> None:
    decision = parse_agent_decision("not-json", "Find the leave policy")
    assert decision.action == "search_documents"


def test_agent_routes_factual_resume_question_to_search() -> None:
    decision = asyncio.run(choose_agent_action("What is my experience?", []))
    assert decision.action == "search_documents"
