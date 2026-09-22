"""Phase-graph orchestration tests (ScriptedInference: no API key in tests).

Scripted routing: trailing '?' = aside, otherwise answer; any sentence yields
facts, so a statement marks its area substantive/answered.
"""

import json
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.graph import DONE_PHASE
from app.agents.inference import ToolCall, ToolCompletion, _purpose_tag
from app.agents.runner import POST_COMPLETE_NO_ANSWER_REPLY, handle_post_complete_message
from app.models.account import Account
from app.models.card import Card
from app.models.message import Message
from app.models.project import Project
from app.services.rag import SCOPE_REFUSAL_TEXT


def _project(client: TestClient, email: str) -> str:
    client.post("/auth/dev-session", json={"display_name": "Yash", "email": email})
    created = client.post(
        "/projects",
        json={"brief": "A clinic booking tool for patients to reschedule visits"},
    )
    assert created.status_code == 201
    return created.json()["id"]


def _last_widget(messages: list[dict], kind: str) -> dict | None:
    for message in reversed(messages):
        if message.get("widget") and message["widget"].get("type") == kind:
            return message["widget"]
    return None


ANSWERS = [
    "Patients miss clinic slots and staff waste hours rescheduling by phone.",
    "First version covers rescheduling only. Cancellations are out.",
    "Clinic managers own it. Front desk staff and patients use it daily.",
]
RISK_CONFIRM = "Yes, that's correct"


def test_planning_interview_to_gate_and_requirements(client: TestClient) -> None:
    project_id = _project(client, "graph@example.com")

    opened = client.get(f"/projects/{project_id}/messages")
    assert opened.status_code == 200
    thread = opened.json()
    assert _last_widget(thread, "coverage_meter") is not None  # read-back mirror
    meter = _last_widget(thread, "coverage_meter")
    assert meter["areas"][0]["hint"]
    assert meter["areas"][0]["label"] == "Business need & vision"
    first_q = _last_widget(thread, "question_card")
    assert first_q is not None
    assert first_q["purpose"] == "business_need"

    for answer in ANSWERS:
        posted = client.post(f"/projects/{project_id}/messages", json={"content": answer})
        assert posted.status_code == 200
        thread = posted.json()
        assert _last_widget(thread, "fact_log") is not None

    risks_q = _last_widget(thread, "question_card")
    assert risks_q is not None
    assert risks_q["purpose"] == "risks"
    assert risks_q["mode"] == "confirm"

    confirmed = client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    assert confirmed.status_code == 200
    thread = confirmed.json()

    readiness_meter = next(
        (
            m["widget"]
            for m in reversed(thread)
            if m.get("widget", {}).get("type") == "coverage_meter"
            and m["widget"].get("readiness_score") is not None
        ),
        None,
    )
    assert readiness_meter is not None
    assert readiness_meter["readiness_score"] >= 0

    panel = _last_widget(thread, "acceptance_panel")
    assert panel is not None
    assert panel["phase"] == "planning"
    assert panel.get("issues") == []
    assert all(status in ("answered", "na") for status in panel["coverage"].values())

    accepted = client.post(f"/projects/{project_id}/gate", json={"action": "accept"})
    assert accepted.status_code == 200
    thread = accepted.json()
    assert _last_widget(thread, "gate_accepted")["accepted_by"] == "Yash"

    project = client.get(f"/projects/{project_id}").json()
    assert project["phase"] == "requirements"

    # D27 seeded handoff: the requirements thread opens itself with its own mirror + question
    reopened = client.get(f"/projects/{project_id}/messages").json()
    next_q = _last_widget(reopened, "question_card")
    assert next_q is not None
    assert next_q["purpose"] == "product_boundary"


def test_aside_and_skip_paths(client: TestClient) -> None:
    project_id = _project(client, "aside@example.com")
    client.get(f"/projects/{project_id}/messages")

    aside = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What do you mean by business need?"},
    )
    thread = aside.json()
    # Aside answered, question NOT advanced: still waiting on business_need.
    # The aside reply itself carries no widget; the still-open question is
    # then re-shown (fix/reask-open-question) so it isn't stranded off-screen.
    assert thread[-2]["widget"] is None
    assert thread[-1]["widget"]["type"] == "question_card"
    assert _last_widget(thread, "question_card")["purpose"] == "business_need"

    skipped = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "", "skipped": True, "bound_to_question": True},
    )
    thread = skipped.json()
    assert any(
        "skipped for now" in m["content"].lower() for m in thread if m["role"] == "assistant"
    )
    assert _last_widget(thread, "question_card")["purpose"] == "scope"

    trace = client.get(f"/projects/{project_id}/retrieval-traces").json()
    kinds = {event["kind"] for event in trace}
    assert "decision" in kinds
    assert "execution" in kinds


def test_bounded_tool_retrieval_fires_for_a_question_never_for_a_statement(
    client: TestClient,
) -> None:
    """D81: the turn node now decides-and-answers via one bounded tool call
    instead of a separate routing call - confirm both branches actually run
    end to end (not just unit-tested in isolation). Only the "decision"
    trace is asserted on: "execution" traces also fire from the unrelated,
    pre-existing next-question-draft retrieval (graph.py's ask node), so
    counting them here would couple this test to that separate mechanism.

    Both messages below must be classified an aside by is_aside_question()
    (area_key set + is_aside_question => force_answer=False) so both reach
    the tool-eligible path at all - an ordinary area answer short-circuits
    straight to force_answer=True and never sees the tool (unchanged from
    decide_retrieval(force_answer=True)'s old behavior, covered separately
    by test_scripted_router_retrieves_for_question_but_not_bound_answer).
    The second message is aside-classified via a starter phrase, not a "?",
    so it still exercises the "answered directly, no tool" branch."""
    project_id = _project(client, "bounded-tool@example.com")
    client.get(f"/projects/{project_id}/messages")

    asked = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What have we already decided about business need?"},
    )
    assert asked.status_code == 200
    decisions = [
        e["detail"]
        for e in client.get(f"/projects/{project_id}/retrieval-traces").json()
        if e["kind"] == "decision"
    ]
    latest = decisions[0]  # newest-first (created_at desc)
    assert latest["reason"] == "tool_call"
    assert latest["should_retrieve"] is True
    assert latest["query"] == "What have we already decided about business need?"

    answered = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "From the notes, what business need was already recorded"},
    )
    assert answered.status_code == 200
    decisions = [
        e["detail"]
        for e in client.get(f"/projects/{project_id}/retrieval-traces").json()
        if e["kind"] == "decision"
    ]
    latest = decisions[0]  # newest-first (created_at desc)
    assert latest["reason"] == "no_tool_call_direct_answer"
    assert latest["should_retrieve"] is False
    assert latest["query"] == ""


def test_out_of_scope_question_is_refused_not_answered(client: TestClient) -> None:
    """D81 scope guardrail: an obviously off-topic aside gets the fixed
    refusal, not a free-answered (potentially hallucinated) reply, and never
    calls search_project_evidence."""
    project_id = _project(client, "scope@example.com")
    client.get(f"/projects/{project_id}/messages")

    asked = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What is the capital of France?"},
    )
    assert asked.status_code == 200
    thread = asked.json()
    # The refusal reply may not be the last message: a still-open question
    # (if any) is re-shown right after it (fix/reask-open-question).
    replies = [m["content"] for m in thread if m["role"] == "assistant"]
    assert any(SCOPE_REFUSAL_TEXT in reply for reply in replies)
    assert any("continue with" in reply.lower() for reply in replies)

    decisions = [
        e["detail"]
        for e in client.get(f"/projects/{project_id}/retrieval-traces").json()
        if e["kind"] == "decision"
    ]
    latest = decisions[0]  # newest-first (created_at desc)
    assert latest["should_retrieve"] is False
    assert latest["in_scope"] is False


def test_readiness_score_hidden_until_gate(client: TestClient) -> None:
    project_id = _project(client, "ready@example.com")
    opened = client.get(f"/projects/{project_id}/messages").json()
    meter = _last_widget(opened, "coverage_meter")
    assert meter is not None
    assert meter.get("readiness_score") is None

    posted = client.post(
        f"/projects/{project_id}/messages",
        json={"content": ANSWERS[0]},
    )
    assert posted.status_code == 200
    meter = _last_widget(posted.json(), "coverage_meter")
    assert meter is not None
    assert meter.get("readiness_score") is None


def test_composer_reply_when_complete_with_tools_fails(client: TestClient, monkeypatch) -> None:
    """A tool-call provider error (e.g. Groq's gpt-oss 'commentary' quirk) must
    not surface as a hard failure - wait() retries once with no tools offered
    (complete_json -> .complete(), a different method), which the scripted
    provider still answers normally."""
    from app.agents.inference import ScriptedInference

    def _boom(self, **kwargs):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(ScriptedInference, "complete_with_tools", _boom)
    project_id = _project(client, "tools-fail@example.com")
    posted = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Patients miss clinic slots and staff waste hours."},
    )
    assert posted.status_code == 200
    assistant = [m for m in posted.json() if m["role"] == "assistant"]
    assert not any("went wrong" in m["content"].lower() for m in assistant)


def test_post_complete_chat_is_grounded_and_scope_checked(client: TestClient, db_session) -> None:
    """D81/B2: post-acceptance free chat used to be one unguarded LLM call
    with no retrieval, no citations, and no grounding judge - it must now
    run the same guardrail as the interview turn node."""
    project_id = _project(client, "post-complete@example.com")
    project = db_session.get(Project, UUID(project_id))
    account = db_session.get(Account, project.created_by_account_id)
    project.phase = DONE_PHASE
    db_session.add(
        Card(
            project_id=project.id,
            kind="requirement",
            coverage_area="scope",
            body="The pilot starts in October.",
        )
    )
    db_session.commit()

    handle_post_complete_message(db_session, project, account, content="When does the pilot start?")
    reply = db_session.scalars(
        select(Message).where(Message.project_id == project.id).order_by(Message.seq.desc())
    ).first()
    assert reply is not None and reply.role == "assistant"
    # The scripted reply never cites [Sn], so the grounding judge - now
    # actually running on this path - abstains rather than passing it
    # through unverified, proving enforce_grounding fires here at all.
    assert "couldn't verify" in reply.content.lower()

    handle_post_complete_message(
        db_session, project, account, content="What is the capital of France?"
    )
    refusal = db_session.scalars(
        select(Message).where(Message.project_id == project.id).order_by(Message.seq.desc())
    ).first()
    assert refusal.content.startswith(SCOPE_REFUSAL_TEXT)


def test_post_complete_chat_records_a_new_fact_instead_of_failing_to_verify_it(
    client: TestClient, db_session
) -> None:
    """D90: a declarative statement after Accept used to be forced through
    the Q&A/grounding path (nothing to verify it against -> a failed-lookup
    reply) with no way to actually record it. It must now be recorded."""
    project_id = _project(client, "post-complete-fact@example.com")
    project = db_session.get(Project, UUID(project_id))
    account = db_session.get(Account, project.created_by_account_id)
    project.phase = DONE_PHASE
    db_session.commit()

    before = {
        c.id
        for c in db_session.scalars(select(Card).where(Card.project_id == project.id)).all()
    }
    handle_post_complete_message(
        db_session,
        project,
        account,
        content="We should also support multi-user login by email.",
        source_message_id="test-source",
    )
    reply = db_session.scalars(
        select(Message).where(Message.project_id == project.id).order_by(Message.seq.desc())
    ).first()
    assert reply is not None and reply.role == "assistant"
    assert "recorded" in reply.content.lower()
    assert "couldn't verify" not in reply.content.lower()

    after = db_session.scalars(select(Card).where(Card.project_id == project.id)).all()
    new_cards = [c for c in after if c.id not in before]
    assert any("multi-user login" in c.body for c in new_cards)


class _EmptyReplyOnGenuineQuestionFakeInference:
    """Regression for a live finding: a genuine post-completion question
    ('what am I trying to achieve with this project?') was classified
    in-scope 'aside' but the model's reply came back empty, which fell
    through to a hardcoded, misleading fallback ("Noted. Use Redraft
    requirements to regenerate docs.") that had nothing to do with the
    question asked. ScriptedInference never produces an empty reply, so
    this hand-written fake reproduces that exact shape: it takes the
    tool-call branch (mirroring the live model calling
    search_project_evidence once) and then returns intent='aside',
    in_scope=True, reply=''."""

    def complete(self, *, model, messages, json_mode=False, max_tokens=None):
        if _purpose_tag(messages) == "post_complete_turn":
            return json.dumps(
                {"reply": "", "in_scope": True, "intent": "aside", "area": "", "facts": []}
            )
        return "{}"

    def complete_with_tools(self, *, model, messages, tools, max_tokens=None):
        tool = tools[0]["function"]
        return ToolCompletion(
            content=None,
            tool_calls=[
                ToolCall(
                    id="fake-1",
                    name=tool["name"],
                    arguments={"query": messages[-1]["content"][:200]},
                )
            ],
        )


def test_post_complete_genuine_question_with_empty_model_reply_gets_neutral_fallback(
    client: TestClient, db_session, monkeypatch
) -> None:
    """Found live: 'what am I trying to achieve with this project?' produced
    'Noted. Use Redraft requirements to regenerate docs.' - the model
    returned an empty reply for a genuine question and it fell through to a
    hardcoded, unrelated instruction. Locks in the fix: an empty reply now
    gets a neutral, grounding-checked fallback instead."""
    project_id = _project(client, "post-complete-empty-reply@example.com")
    project = db_session.get(Project, UUID(project_id))
    account = db_session.get(Account, project.created_by_account_id)
    project.phase = DONE_PHASE
    # No retrievable evidence, so enforce_grounding's short-circuit (no hits
    # -> text passed through unchanged) is what's under test here, not the
    # grounding judge itself - the project brief is auto-ingested as a card
    # at creation, so it must be cleared for retrieval to return no hits.
    for card in db_session.scalars(select(Card).where(Card.project_id == project.id)).all():
        db_session.delete(card)
    db_session.commit()

    monkeypatch.setattr(
        "app.agents.runner.get_inference",
        lambda settings: _EmptyReplyOnGenuineQuestionFakeInference(),
    )
    handle_post_complete_message(
        db_session,
        project,
        account,
        content="What am I trying to achieve with this project?",
    )
    reply = db_session.scalars(
        select(Message).where(Message.project_id == project.id).order_by(Message.seq.desc())
    ).first()
    assert reply is not None and reply.role == "assistant"
    assert reply.content == POST_COMPLETE_NO_ANSWER_REPLY
    assert "redraft requirements to regenerate docs" not in reply.content.lower()


def test_skipped_area_revisited_before_gate(client: TestClient) -> None:
    project_id = _project(client, "skip-revisit@example.com")
    client.get(f"/projects/{project_id}/messages")
    skipped = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "", "skipped": True, "bound_to_question": True},
    ).json()
    meter = _last_widget(skipped, "coverage_meter")
    assert meter is not None
    statuses = {a["key"]: a["status"] for a in meter["areas"]}
    assert statuses["business_need"] == "skipped"
    thread: list[dict] = []
    for answer in ANSWERS:
        thread = client.post(f"/projects/{project_id}/messages", json={"content": answer}).json()
    # The last ANSWERS turn closes "risks" and the revisit prompt for the
    # skipped area becomes the active question in this same response - do
    # NOT post another message here: with defer_resume correctly cleared
    # (see graph.py ask()'s from_revisit_skip branch), a further message
    # now genuinely answers that revisit question instead of being dropped,
    # which would close business_need and reach the gate - the opposite of
    # what this test is checking.
    mid_statuses = {a["key"]: a["status"] for a in _last_widget(thread, "coverage_meter")["areas"]}
    assert mid_statuses.get("business_need") == "skipped"
    assert _last_widget(thread, "acceptance_panel") is None
    q = _last_widget(thread, "question_card")
    assert q is not None
    assert q["purpose"] == "business_need"
    assert any(
        "revisit" in m["content"].lower() or "skipped" in m["content"].lower()
        for m in thread
        if m["role"] == "assistant"
    )


def test_typed_idk_stays_on_area(client: TestClient) -> None:
    project_id = _project(client, "skip-delegate@example.com")
    client.get(f"/projects/{project_id}/messages")
    thread = client.post(
        f"/projects/{project_id}/messages", json={"content": "i don't know"}
    ).json()
    assert not any("we'll skip" in m["content"] for m in thread if m["role"] == "assistant")
    assert _last_widget(thread, "question_card")["purpose"] == "business_need"

    delegated = client.post(
        f"/projects/{project_id}/messages", json={"content": "you decide"}
    ).json()
    q = _last_widget(delegated, "question_card")
    assert q is not None
    assert q["purpose"] == "business_need"
    assert any(
        "you asked me to decide" in m["content"].lower()
        or "need more detail" in m["content"].lower()
        for m in delegated
        if m["role"] == "assistant"
    )


def test_confirm_yes_closes_area(client: TestClient) -> None:
    project_id = _project(client, "confirm-yes@example.com")
    thread = client.get(f"/projects/{project_id}/messages").json()
    first = _last_widget(thread, "question_card")
    assert first is not None
    closed = client.post(
        f"/projects/{project_id}/messages", json={"content": "Yes, that's correct"}
    )
    thread = closed.json()
    assert any("covered" in m["content"] for m in thread if m["role"] == "assistant")
    nxt = _last_widget(thread, "question_card")
    assert nxt is not None
    assert nxt["purpose"] != first["purpose"]
    assert nxt.get("options")


def test_mostly_correct_keeps_area_open(client: TestClient) -> None:
    project_id = _project(client, "mostly-correct@example.com")
    client.get(f"/projects/{project_id}/messages")
    before = client.post(
        f"/projects/{project_id}/messages",
        json={"content": ANSWERS[0]},
    ).json()
    scope_card = _last_widget(before, "question_card")
    assert scope_card is not None
    assert scope_card["purpose"] == "scope"

    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Mostly correct, but I'd add..."},
    ).json()
    q = _last_widget(thread, "question_card")
    assert q is not None
    assert q["purpose"] == "scope"
    new_msgs = thread[len(before) :]
    assert not any(
        m["content"].endswith(": covered.") for m in new_msgs if m["role"] == "assistant"
    )


def test_delegate_on_confirm_accepts_proposal(client: TestClient) -> None:
    project_id = _project(client, "delegate-confirm@example.com")
    client.get(f"/projects/{project_id}/messages")
    for answer in ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "You decide for me"},
    ).json()
    assert any("You asked me to decide" in m["content"] for m in thread if m["role"] == "assistant")
    assert _last_widget(thread, "question_card") is not None


def test_bound_chip_answer_not_treated_as_ui_command(client: TestClient) -> None:
    """Failure-path chip text must record as an answer, not clear the chat."""
    project_id = _project(client, "bound-chip@example.com")
    client.get(f"/projects/{project_id}/messages")
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={
            "content": "Clear the input and require me to start over",
            "bound_to_question": True,
        },
    ).json()
    assistant = [m for m in thread if m["role"] == "assistant"]
    assert assistant
    joined = " ".join(m["content"] for m in assistant[-4:])
    assert "Input cleared" not in joined
    assert "Retrieved context" not in joined
    assert (
        _last_widget(thread, "fact_log") is not None
        or "recorded" in joined.lower()
        or "Got it" in joined
    )


def _new_assistant_messages(thread: list[dict], *, after: int) -> list[dict]:
    return [m for m in thread[after:] if m.get("role") == "assistant"]


def test_gate_revise_emits_single_question(client: TestClient) -> None:
    project_id = _project(client, "gate-single-q@example.com")
    _reach_risks_confirm(client, project_id)
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    before = len(client.get(f"/projects/{project_id}/messages").json())
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "revise risks — they feel thin"},
    ).json()
    new_assistant = _new_assistant_messages(thread, after=before)
    question_cards = [
        m for m in new_assistant if (m.get("widget") or {}).get("type") == "question_card"
    ]
    assert len(new_assistant) == 1
    assert len(question_cards) == 1
    assert question_cards[0]["widget"]["purpose"] == "risks"
    assert question_cards[0]["widget"]["mode"] in ("ask", "confirm")


def test_gate_revise_reopens_area(client: TestClient) -> None:
    project_id = _project(client, "revise@example.com")
    client.get(f"/projects/{project_id}/messages")
    for answer in ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})

    revised = client.post(
        f"/projects/{project_id}/gate",
        json={"action": "revise", "area": "risks", "content": "risks feel thin"},
    )
    thread = revised.json()
    # The revise acknowledgement is LLM-worded (PR #33); assert the durable
    # behavior instead: the gate did not accept and the area reopened.
    assert _last_widget(thread, "gate_accepted") is None
    assert _last_widget(thread, "question_card")["purpose"] == "risks"
    assert _last_widget(thread, "question_card")["mode"] in ("ask", "confirm")


def _reach_risks_confirm(client: TestClient, project_id: str) -> None:
    client.get(f"/projects/{project_id}/messages")
    for answer in ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})


def test_delegate_you_can_decide_not_skip(client: TestClient) -> None:
    project_id = _project(client, "you-can-decide@example.com")
    client.get(f"/projects/{project_id}/messages")
    client.post(f"/projects/{project_id}/messages", json={"content": "i don't know"})
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "i dont know, maybe you can decide"},
    ).json()
    joined = " ".join(m["content"] for m in thread if m["role"] == "assistant")
    assert "we'll skip scope" not in joined.lower()


def test_process_meta_does_not_record_facts(client: TestClient) -> None:
    project_id = _project(client, "process-meta@example.com")
    client.get(f"/projects/{project_id}/messages")
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "i want to give multiple choice options"},
    ).json()
    assert _last_widget(thread, "fact_log") is None


def test_gate_free_text_qa(client: TestClient) -> None:
    project_id = _project(client, "gate-qa@example.com")
    _reach_risks_confirm(client, project_id)
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What does the draft say about scope?"},
    ).json()
    assert _last_widget(thread, "gate_accepted") is None
    assert any(m["role"] == "assistant" for m in thread)


def test_gate_free_text_revise(client: TestClient) -> None:
    project_id = _project(client, "gate-nl-revise@example.com")
    _reach_risks_confirm(client, project_id)
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "revise risks — they feel thin"},
    ).json()
    assert _last_widget(thread, "gate_accepted") is None
    assert _last_widget(thread, "question_card")["purpose"] == "risks"
    assert _last_widget(thread, "question_card")["mode"] in ("ask", "confirm")


def test_conflict_delegate_applies_current(client: TestClient, db_session) -> None:
    from uuid import UUID

    from app.models.project import Project
    from app.services import belief as belief_service
    from app.services.cards import record_facts

    project_id = _project(client, "conflict-delegate@example.com")
    project = db_session.get(Project, UUID(project_id))
    assert project is not None
    record_facts(
        db_session,
        project,
        area="scope",
        facts=["Scope includes mobile apps"],
        source_message_id="seed:a",
    )
    record_facts(
        db_session,
        project,
        area="scope",
        facts=["Scope excludes mobile apps"],
        source_message_id="seed:b",
    )
    assert len(belief_service.list_conflicts(db_session, project)) == 1

    thread = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "you decide"},
    ).json()
    assert any("kept" in m["content"].lower() for m in thread if m["role"] == "assistant")
    assert len(belief_service.list_conflicts(db_session, project)) == 0


def test_conflict_gate_blocks_until_resolved(client: TestClient, db_session) -> None:
    from uuid import UUID

    from app.models.project import Project
    from app.services import belief as belief_service
    from app.services.cards import record_facts

    project_id = _project(client, "conflict-gate@example.com")
    project = db_session.get(Project, UUID(project_id))
    assert project is not None
    record_facts(
        db_session,
        project,
        area="scope",
        facts=["Scope includes mobile apps"],
        source_message_id="seed:a",
    )
    record_facts(
        db_session,
        project,
        area="scope",
        facts=["Scope excludes mobile apps"],
        source_message_id="seed:b",
    )
    assert belief_service.list_conflicts(db_session, project)

    _reach_risks_confirm(client, project_id)
    thread = client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM}).json()
    assert any(
        "resolve" in m["content"] and "conflict" in m["content"].lower()
        for m in thread
        if m["role"] == "assistant"
    )
    assert _last_widget(thread, "acceptance_panel") is None
