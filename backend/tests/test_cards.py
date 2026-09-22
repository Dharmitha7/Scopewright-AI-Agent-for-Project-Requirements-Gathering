"""Cards/strings/snapshots behind KnowledgePort (D17, D22, D45-D47).

Keeps the existing agent-lane behavior (test_agents.py) green and adds
storage-lane assertions: facts land as real cards/strings, the digest reads
from cards, and gate accept promotes + freezes a snapshot.
"""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.knowledge import CardKnowledge
from app.models.card import Card
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.models.string import CardString


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


PLANNING_ANSWERS = [
    "Patients miss clinic slots and staff waste hours rescheduling by phone.",
    "First version covers rescheduling only. Cancellations are out.",
    "Clinic managers own it. Front desk staff and patients use it daily.",
]
RISK_CONFIRM = "Yes, that's correct"

REQUIREMENTS_AREA_COUNT = 9  # templates.REQUIREMENTS.areas


def test_answers_become_cards_with_source_and_supported_by(
    client: TestClient, db_session: Session
) -> None:
    project_id = _project(client, "cards@example.com")
    client.get(f"/projects/{project_id}/messages")  # trigger read-back + first question

    posted = client.post(
        f"/projects/{project_id}/messages", json={"content": PLANNING_ANSWERS[0]}
    )
    assert posted.status_code == 200

    # Optional GET /projects/{id}/cards surfaces the same rows the API just wrote.
    listed = client.get(f"/projects/{project_id}/cards")
    assert listed.status_code == 200
    kinds = {c["kind"] for c in listed.json()}
    assert "business_need" in kinds  # AREA_KIND["planning"]["business_need"]

    pid = UUID(project_id)
    fact_cards = db_session.scalars(
        select(Card).where(Card.project_id == pid, Card.kind == "business_need")
    ).all()
    assert len(fact_cards) >= 1
    for card in fact_cards:
        assert card.coverage_area == "business_need"
        assert card.status == "candidate"

    source_cards = db_session.scalars(
        select(Card).where(Card.project_id == pid, Card.kind == "source")
    ).all()
    # Brief, the chat answer, and possibly an AI proposal source if the next
    # area (scope) is synthesize-then-confirm in the same turn.
    assert len(source_cards) >= 2
    assert "brief" in {c.body for c in source_cards}
    chat_sources = [c for c in source_cards if c.body != "brief"]
    assert chat_sources

    strings = db_session.scalars(
        select(CardString).where(
            CardString.project_id == pid,
            CardString.kind == "supported-by",
            CardString.from_card_id.in_([c.id for c in fact_cards]),
        )
    ).all()
    assert len(strings) >= len(fact_cards)


def test_scope_area_maps_to_constraint_kind(client: TestClient, db_session: Session) -> None:
    project_id = _project(client, "scope@example.com")
    client.get(f"/projects/{project_id}/messages")
    client.post(f"/projects/{project_id}/messages", json={"content": PLANNING_ANSWERS[0]})
    posted = client.post(f"/projects/{project_id}/messages", json={"content": PLANNING_ANSWERS[1]})
    assert posted.status_code == 200

    pid = UUID(project_id)
    scope_cards = db_session.scalars(
        select(Card).where(Card.project_id == pid, Card.coverage_area == "scope")
    ).all()
    assert scope_cards
    assert all(c.kind == "constraint" for c in scope_cards)


def test_digest_reads_from_cards_not_widgets(client: TestClient, db_session: Session) -> None:
    project_id = _project(client, "digest@example.com")
    client.get(f"/projects/{project_id}/messages")
    client.post(f"/projects/{project_id}/messages", json={"content": PLANNING_ANSWERS[0]})

    project = db_session.get(Project, UUID(project_id))
    assert project is not None
    digest = CardKnowledge(db_session, project).planning_digest()
    assert "[business_need]" in digest
    assert "Patients miss clinic slots" in digest


def test_gate_accept_promotes_cards_and_freezes_snapshot(
    client: TestClient, db_session: Session
) -> None:
    project_id = _project(client, "gate@example.com")
    pid = UUID(project_id)
    client.get(f"/projects/{project_id}/messages")
    for answer in PLANNING_ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})

    accepted = client.post(f"/projects/{project_id}/gate", json={"action": "accept"})
    assert accepted.status_code == 200

    planning_snapshots = db_session.scalars(
        select(Snapshot).where(Snapshot.project_id == pid, Snapshot.phase == "planning")
    ).all()
    assert len(planning_snapshots) == 1
    snapshot = planning_snapshots[0]
    assert snapshot.card_versions  # non-empty pointer list
    assert all({"card_id", "version"} <= set(p) for p in snapshot.card_versions)

    planning_areas = {"business_need", "scope", "stakeholders", "risks"}
    promoted = db_session.scalars(
        select(Card).where(Card.project_id == pid, Card.coverage_area.in_(planning_areas))
    ).all()
    assert promoted
    assert all(c.status == "accepted" for c in promoted)

    # Requirements now owns the thread; answer all 9 areas and accept its gate too.
    for i in range(REQUIREMENTS_AREA_COUNT):
        resp = client.post(
            f"/projects/{project_id}/messages",
            json={"content": f"Detail number {i} for this area of the system."},
        )
        assert resp.status_code == 200

    accepted_req = client.post(
        f"/projects/{project_id}/gate",
        json={
            "action": "select_packs",
            "pack_ids": ["requirements_summary", "quality_gap_report"],
            "pack_mode": "separate",
        },
    )
    assert accepted_req.status_code == 200
    accepted_req = client.post(f"/projects/{project_id}/gate", json={"action": "accept"})
    assert accepted_req.status_code == 200

    requirements_snapshots = db_session.scalars(
        select(Snapshot).where(Snapshot.project_id == pid, Snapshot.phase == "requirements")
    ).all()
    assert len(requirements_snapshots) == 1
    assert requirements_snapshots[0].narratives is not None
    assert requirements_snapshots[0].narratives["mode"] == "separate"


def test_snapshot_view_is_deterministic_markdown(client: TestClient) -> None:
    project_id = _project(client, "view@example.com")
    client.get(f"/projects/{project_id}/messages")
    for answer in PLANNING_ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    client.post(f"/projects/{project_id}/gate", json={"action": "accept"})

    views = client.get(f"/projects/{project_id}/snapshots")
    assert views.status_code == 200
    rows = views.json()
    assert len(rows) == 1
    assert rows[0]["phase"] == "planning"
    assert rows[0]["document"] == "Project Charter"
    assert rows[0]["body"].startswith("# Project Charter")
    assert "- Patients miss clinic slots" in rows[0]["body"]
