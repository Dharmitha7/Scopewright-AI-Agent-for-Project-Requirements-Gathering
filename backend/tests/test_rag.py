from app.services.rag import SCOPE_REFUSAL_TEXT, scope_refusal_reply


def test_scope_refusal_reply_includes_resume_nudge() -> None:
    reply = scope_refusal_reply(area_label="Scope & exclusions")
    assert SCOPE_REFUSAL_TEXT in reply
    assert "Scope & exclusions" in reply
    assert "continue with" in reply.lower()


def test_scope_refusal_reply_without_area() -> None:
    reply = scope_refusal_reply()
    assert SCOPE_REFUSAL_TEXT in reply
    assert "interview question" in reply.lower()
