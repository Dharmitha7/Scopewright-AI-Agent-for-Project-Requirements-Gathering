from app.agents.inference import ScriptedInference
from app.services import conflict_advice as conflict_advice_service


def test_advise_single_conflict_both_question():
    row = {
        "id": "c1",
        "card_a": {"id": "a1", "body": "Invoice only", "status": "candidate"},
        "card_b": {"id": "b1", "body": "Stripe cards", "status": "candidate"},
    }
    advice = conflict_advice_service.advise_single_conflict(
        ScriptedInference(),
        model="scripted",
        row=row,
        user_message="can we have both?",
    )
    assert advice["pick"] == ""
    assert "only one" in advice["reply"].lower() or "keep" in advice["reply"].lower()


def test_advise_single_conflict_delegate_pick():
    row = {
        "id": "c1",
        "card_a": {"id": "a1", "body": "Invoice only", "status": "candidate"},
        "card_b": {"id": "b1", "body": "Stripe cards", "status": "candidate"},
    }
    advice = conflict_advice_service.advise_single_conflict(
        ScriptedInference(),
        model="scripted",
        row=row,
        user_message="you decide",
    )
    assert advice["pick"] in ("a", "b")
    body = conflict_advice_service.format_advice_message(advice)
    assert "confirm" in body.lower()
    assert "kept" not in body.lower()
