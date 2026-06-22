from app.services.memory import build_contextual_query, conversation_title


def test_contextual_query_uses_recent_user_messages() -> None:
    history = [
        {"role": "user", "content": "Tell me about vacation policy"},
        {"role": "assistant", "content": "Employees receive annual leave."},
        {"role": "user", "content": "Who is eligible?"},
    ]

    query = build_contextual_query("What about new employees?", history)

    assert "vacation policy" in query
    assert "Who is eligible?" in query
    assert query.endswith("What about new employees?")
    assert "Employees receive" not in query


def test_conversation_title_is_normalized_and_bounded() -> None:
    assert conversation_title("  How   does memory work?  ") == "How does memory work?"
    assert len(conversation_title("x" * 100)) == 80
