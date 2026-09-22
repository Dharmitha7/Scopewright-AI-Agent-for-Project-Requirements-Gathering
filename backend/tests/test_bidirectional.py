"""Bidirectional Planning <-> Requirements editing (D89)."""

import json
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.inference import ToolCompletion, _purpose_tag
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.services import cards as cards_service
from tests.test_e2e_v1 import REQUIREMENTS_ANSWERS, _answer_all, _complete_planning, _session


def _accept_planning(client: TestClient, project_id: str) -> None:
    _complete_planning(client, project_id)
    assert client.post(f"/projects/{project_id}/gate", json={"action": "accept"}).status_code == 200


def _last_widget(messages: list[dict], kind: str) -> dict | None:
    for message in reversed(messages):
        if message.get("widget") and message["widget"].get("type") == kind:
            return message["widget"]
    return None


def test_planning_redraft_requires_a_prior_accept(client: TestClient) -> None:
    project_id = _session(client, "redraft-too-early@example.com")
    client.get(f"/projects/{project_id}/messages")
    resp = client.post(
        f"/projects/{project_id}/gate",
        json={"action": "planning_redraft", "tab": "planning"},
    )
    assert resp.status_code == 422


def test_planning_redraft_targets_one_area_not_full_reinterview(client: TestClient) -> None:
    project_id = _session(client, "redraft-one-area@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)
    assert client.get(f"/projects/{project_id}").json()["phase"] == "requirements"

    resp = client.post(
        f"/projects/{project_id}/gate",
        json={"action": "planning_redraft", "tab": "planning", "area": "risks"},
    )
    assert resp.status_code == 200
    card = _last_widget(resp.json(), "question_card")
    assert card is not None
    assert card["purpose"] == "risks"

    # Still a side excursion - project.phase never moved off requirements.
    assert client.get(f"/projects/{project_id}").json()["phase"] == "requirements"


def test_planning_redraft_second_accept_keeps_every_area(
    client: TestClient, db_session
) -> None:
    """Regression for the freeze_snapshot() pointer-set bug found in review:
    a targeted redraft of one area must not drop the other areas from the
    new snapshot's rendered document."""
    project_id = _session(client, "redraft-second-accept@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)

    client.post(
        f"/projects/{project_id}/gate",
        json={"action": "planning_redraft", "tab": "planning", "area": "risks"},
    )
    answered = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "New risk: the calendar vendor may deprecate its API.", "tab": "planning"},
    )
    assert answered.status_code == 200

    accepted = client.post(
        f"/projects/{project_id}/gate", json={"action": "accept", "tab": "planning"}
    )
    assert accepted.status_code == 200

    project = client.get(f"/projects/{project_id}").json()
    assert project["phase"] == "requirements"  # un-changed by the redraft's own accept

    row = db_session.get(Project, UUID(project["id"]))
    assert row.planning_doc_version == 2
    assert row.planning_redraft_active is False

    planning_snaps = db_session.scalars(
        select(Snapshot)
        .where(Snapshot.project_id == row.id, Snapshot.phase == "planning")
        .order_by(Snapshot.created_at.asc())
    ).all()
    assert len(planning_snaps) == 2
    rendered = cards_service.render_snapshot(db_session, planning_snaps[-1])
    # Every original Planning area must still be present, not just risks.
    assert "clinic slots" in rendered.lower()  # business_need
    assert "rescheduling only" in rendered.lower()  # scope
    assert "clinic managers" in rendered.lower()  # stakeholders
    assert "deprecate" in rendered.lower()  # the newly redrafted risk


def test_planning_redraft_from_done_leaves_phase_unchanged(client: TestClient) -> None:
    project_id = _session(client, "redraft-from-done@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)
    _answer_all(client, project_id, REQUIREMENTS_ANSWERS)
    client.post(
        f"/projects/{project_id}/gate",
        json={
            "action": "select_packs",
            "pack_ids": ["requirements_summary"],
            "pack_mode": "separate",
        },
    )
    client.post(f"/projects/{project_id}/gate", json={"action": "accept"})
    assert client.get(f"/projects/{project_id}").json()["phase"] == "done"

    client.post(
        f"/projects/{project_id}/gate",
        json={"action": "planning_redraft", "tab": "planning", "area": "risks"},
    )
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "New risk: staffing shortage during rollout.", "tab": "planning"},
    )
    accepted = client.post(
        f"/projects/{project_id}/gate", json={"action": "accept", "tab": "planning"}
    )
    assert accepted.status_code == 200
    # Un-completing a DONE project as a side effect would be a much worse
    # bug than the one this feature fixes.
    assert client.get(f"/projects/{project_id}").json()["phase"] == "done"


def test_planning_thread_key_matches_graph_checkpoint_thread(
    client: TestClient, db_session
) -> None:
    from app.agents import runner
    from app.models.account import Account
    from app.services.chat_threads import planning_thread_key

    project_id = _session(client, "thread-key-parity@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)
    client.post(
        f"/projects/{project_id}/gate",
        json={"action": "planning_redraft", "tab": "planning", "area": "risks"},
    )

    project = db_session.get(Project, UUID(project_id))
    account = db_session.scalar(select(Account).where(Account.id == project.created_by_account_id))
    _graph, config = runner._graph(db_session, project, account, phase_override="planning")
    assert config["configurable"]["thread_id"] == planning_thread_key(
        project.id, project.planning_doc_version
    )


class _PlanningRedirectFakeInference:
    """Deterministic stand-in forcing on_topic=False + a fact on the turn
    call, then a true redirect verdict - exercises graph.py's new branch
    without touching the shared ScriptedInference heuristics other tests
    depend on (ScriptedInference never sets on_topic for "turn", by design)."""

    def complete(self, *, model, messages, json_mode=False, max_tokens=None):
        purpose = _purpose_tag(messages)
        if purpose == "planning_redirect_check":
            return json.dumps(
                {
                    "belongs_to_planning": True,
                    "planning_area": "scope",
                    "reason": "This changes the overall v1 scope, a Planning-level concern.",
                }
            )
        if purpose in ("turn", "turn_confirm"):
            return json.dumps(
                {
                    "intent": "answer",
                    "kind": "answer",
                    "in_scope": True,
                    "on_topic": False,
                    "answer_completeness": "complete",
                    "confirmed": False,
                    "facts": [{"text": "We should also support enterprise customers."}],
                    "area_covered": False,
                    "gaps": [],
                    "reply": "Noted.",
                    "followup_prompt": "",
                    "followup_options": [],
                }
            )
        return "{}"

    def complete_with_tools(self, *, model, messages, tools, max_tokens=None):
        return ToolCompletion(content=self.complete(model=model, messages=messages), tool_calls=[])


class _PlanningRedirectViaAsideFakeInference:
    """D90 regression: found live, a genuine stakeholder-change statement
    ("the hospital board wants final sign-off") got classified as an aside
    with in_scope=False (fully out of scope), not answer/on_topic=false -
    the original gate only checked the latter, so this path reached the flat
    scope-refusal reply instead of ever considering a Planning redirect."""

    def complete(self, *, model, messages, json_mode=False, max_tokens=None):
        purpose = _purpose_tag(messages)
        if purpose == "planning_redirect_check":
            return json.dumps(
                {
                    "belongs_to_planning": True,
                    "planning_area": "stakeholders",
                    "reason": "This changes who the project sponsor is, a Planning-level concern.",
                }
            )
        if purpose in ("turn", "turn_confirm"):
            return json.dumps(
                {
                    "intent": "aside",
                    "kind": "aside",
                    "in_scope": False,
                    "on_topic": False,
                    "answer_completeness": "unclear",
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "gaps": [],
                    "reply": "That's outside what I can help with here.",
                    "followup_prompt": "",
                    "followup_options": [],
                }
            )
        return "{}"

    def complete_with_tools(self, *, model, messages, tools, max_tokens=None):
        return ToolCompletion(content=self.complete(model=model, messages=messages), tool_calls=[])


def test_requirements_off_topic_fact_offers_planning_redirect(
    client: TestClient, db_session, monkeypatch
) -> None:
    project_id = _session(client, "redirect-suggestion@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)

    # Only fake the model for the one Requirements turn under test - Planning
    # above needed the real ScriptedInference to actually progress and accept.
    monkeypatch.setattr(
        "app.agents.runner.get_inference", lambda settings: _PlanningRedirectFakeInference()
    )
    before = {c["id"] for c in client.get(f"/projects/{project_id}/cards").json()}
    resp = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Actually we should also support enterprise customers, not just SMBs."},
    )
    assert resp.status_code == 200
    widget = _last_widget(resp.json(), "phase_redirect_suggestion")
    assert widget is not None
    assert widget["planning_area"] == "scope"

    after = {c["id"] for c in client.get(f"/projects/{project_id}/cards").json()}
    assert after == before  # nothing recorded either way until the human decides


def test_requirements_aside_out_of_scope_still_offers_planning_redirect(
    client: TestClient, monkeypatch
) -> None:
    """D90: a Planning-shaped statement classified as aside/in_scope=false
    (not answer/on_topic=false) must still get the redirect offer instead of
    the flat scope-refusal reply."""
    project_id = _session(client, "redirect-via-aside@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)

    monkeypatch.setattr(
        "app.agents.runner.get_inference",
        lambda settings: _PlanningRedirectViaAsideFakeInference(),
    )
    resp = client.post(
        f"/projects/{project_id}/messages",
        json={
            "content": "The hospital board wants final sign-off now, not just clinic admin."
        },
    )
    assert resp.status_code == 200
    widget = _last_widget(resp.json(), "phase_redirect_suggestion")
    assert widget is not None
    assert widget["planning_area"] == "stakeholders"
    # The flat scope-refusal text must not have been used instead.
    replies = [m["content"] for m in resp.json() if m["role"] == "assistant"]
    assert not any("outside what I can help with" in r for r in replies)


def test_requirements_stale_since_after_planning_redraft(client: TestClient) -> None:
    project_id = _session(client, "stale-signal@example.com")
    client.get(f"/projects/{project_id}/messages")
    _accept_planning(client, project_id)
    _answer_all(client, project_id, REQUIREMENTS_ANSWERS)
    client.post(
        f"/projects/{project_id}/gate",
        json={
            "action": "select_packs",
            "pack_ids": ["requirements_summary"],
            "pack_mode": "separate",
        },
    )
    client.post(f"/projects/{project_id}/gate", json={"action": "accept"})

    state = client.get(f"/projects/{project_id}/chat-state", params={"tab": "requirements"}).json()
    assert state["requirements_stale_since"] is None

    client.post(
        f"/projects/{project_id}/gate",
        json={"action": "planning_redraft", "tab": "planning", "area": "risks"},
    )
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "New risk: staffing shortage during rollout.", "tab": "planning"},
    )
    client.post(f"/projects/{project_id}/gate", json={"action": "accept", "tab": "planning"})

    state = client.get(f"/projects/{project_id}/chat-state", params={"tab": "requirements"}).json()
    assert state["requirements_stale_since"] is not None
