"""End-to-end v1 lifecycle tests."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.account import Account
from app.models.job import Job
from app.models.project import Project
from app.services import ingestion as ingestion_service
from tests.sse import parse_sse

PLANNING_ANSWERS = [
    "Patients miss clinic slots and staff waste hours rescheduling by phone.",
    "First version covers rescheduling only. Cancellations are out.",
    "Clinic managers own it. Front desk staff and patients use it daily.",
]
RISK_CONFIRM = "Yes, that's correct"

REQUIREMENTS_ANSWERS = [
    "Boundary matches the accepted charter rescheduling scope.",
    "Patients reschedule visits. Front desk staff assist when needed.",
    "Patient opens app, picks a slot, confirms reschedule end to end.",
    "When the calendar API fails we show retry and keep the old slot.",
    "Slots must respect clinic business hours and provider capacity rules.",
    "Core entities are patients, appointments, and clinic calendars.",
    "Integrates with the clinic calendar via a REST API with OAuth.",
    "Page load under two seconds. Supports five hundred daily reschedules.",
    "HIPAA-style handling for patient identifiers in v1.",
]


def _session(client: TestClient, email: str) -> str:
    client.post("/auth/dev-session", json={"display_name": "E2E", "email": email})
    project = client.post(
        "/projects",
        json={"brief": "Clinic rescheduling portal for patients and front desk staff"},
    ).json()
    return project["id"]


def _answer_all(client: TestClient, project_id: str, answers: list[str]) -> None:
    for answer in answers:
        res = client.post(f"/projects/{project_id}/messages", json={"content": answer})
        assert res.status_code == 200


def _complete_planning(client: TestClient, project_id: str) -> None:
    _answer_all(client, project_id, PLANNING_ANSWERS)
    res = client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    assert res.status_code == 200


def test_full_v1_lifecycle(client: TestClient) -> None:
    project_id = _session(client, "e2e-full@example.com")
    client.get(f"/projects/{project_id}/messages")

    _complete_planning(client, project_id)
    assert client.post(f"/projects/{project_id}/gate", json={"action": "accept"}).status_code == 200
    assert client.get(f"/projects/{project_id}").json()["phase"] == "requirements"

    _answer_all(client, project_id, REQUIREMENTS_ANSWERS)
    assert (
        client.post(
            f"/projects/{project_id}/gate",
            json={
                "action": "select_packs",
                "pack_ids": ["requirements_summary", "epics_features_stories"],
                "pack_mode": "separate",
            },
        ).status_code
        == 200
    )
    assert client.post(f"/projects/{project_id}/gate", json={"action": "accept"}).status_code == 200

    project = client.get(f"/projects/{project_id}").json()
    assert project["phase"] == "done"

    snapshots = client.get(f"/projects/{project_id}/snapshots").json()
    assert len(snapshots) >= 2
    assert any(s["phase"] == "planning" for s in snapshots)
    assert any(s["phase"] == "requirements" for s in snapshots)

    cards = client.get(f"/projects/{project_id}/cards").json()
    assert len(cards) >= len(PLANNING_ANSWERS)

    # D83: free-form chat after done (not a hard stop).
    chat = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What scope did we lock for v1?"},
    )
    assert chat.status_code == 200
    assert client.get(f"/projects/{project_id}").json()["phase"] == "done"
    assert any(m["role"] == "assistant" for m in chat.json())
    assert client.get(f"/projects/{project_id}").json()["requirements_doc_version"] == 1

    # D83: redraft → generate → accept bumps version, stays done.
    redraft = client.post(f"/projects/{project_id}/gate", json={"action": "redraft"})
    assert redraft.status_code == 200
    assert client.get(f"/projects/{project_id}").json()["phase"] == "requirements"
    assert _last_widget(redraft.json(), "deliverable_picker") is not None

    assert (
        client.post(
            f"/projects/{project_id}/gate",
            json={
                "action": "select_packs",
                "pack_ids": ["requirements_summary"],
                "pack_mode": "combined",  # coerced to separate (D84)
            },
        ).status_code
        == 200
    )
    assert client.post(f"/projects/{project_id}/gate", json={"action": "accept"}).status_code == 200
    after = client.get(f"/projects/{project_id}").json()
    assert after["phase"] == "done"
    assert after["requirements_doc_version"] == 2
    snaps = client.get(f"/projects/{project_id}/snapshots").json()
    req_snaps = [s for s in snaps if s["phase"] == "requirements"]
    assert len(req_snaps) >= 2


def _last_widget(messages: list[dict], kind: str) -> dict | None:
    for message in reversed(messages):
        if message.get("widget") and message["widget"].get("type") == kind:
            return message["widget"]
    return None


def test_message_stream_sse(client: TestClient) -> None:
    project_id = _session(client, "e2e-stream@example.com")
    client.get(f"/projects/{project_id}/messages")

    res = client.post(
        f"/projects/{project_id}/messages/stream",
        json={"content": PLANNING_ANSWERS[0]},
    )
    assert res.status_code == 200
    events = parse_sse(res.text)
    kinds = [e.event for e in events]
    assert kinds[0] == "RUN_STARTED"
    assert "MESSAGE" in kinds
    assert kinds[-1] == "RUN_FINISHED"
    message_events = [e for e in events if e.event == "MESSAGE"]
    assert any(e.data.get("role") == "assistant" for e in message_events)


def test_upload_and_ingest(client: TestClient, db_session) -> None:
    project_id = _session(client, "e2e-upload@example.com")
    project = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project,
        account_id=account_id,
        filename="notes.txt",
        content_type="text/plain",
        body=b"Stakeholders include clinic managers and front desk leads.",
        speaker_name=None,
    )
    jobs = db_session.scalars(select(Job).where(Job.kind == ingestion_service.INGEST_KIND)).all()
    job = next(j for j in reversed(jobs) if j.payload.get("upload_id") == str(upload.id))
    ingestion_service.process_ingest_job(db_session, job)

    cards = client.get(f"/projects/{project_id}/cards").json()
    assert len(cards) >= 1
