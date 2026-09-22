from uuid import UUID

from sqlalchemy import select

from app.models.account import Account
from app.models.card import Card
from app.models.evidence_chunk import EvidenceChunk
from app.models.job import Job
from app.models.message import Message
from app.models.project import Project
from app.services import ingestion as ingestion_service


def _session(client):
    client.post(
        "/auth/dev-session",
        json={"display_name": "Ingest", "email": "ingest@example.com"},
    )
    project = client.post("/projects", json={"brief": "Upload test project"}).json()
    return project["id"]


def test_upload_endpoint_queues_job(client):
    project_id = _session(client)
    content = b"Stakeholders include the CFO. Scope excludes mobile."
    response = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("notes.txt", content, "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["status"] == "queued"


def test_upload_content_returns_original_bytes(client):
    project_id = _session(client)
    content = b"Original evidence body for preview."
    uploaded = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("preview.txt", content, "text/plain")},
    ).json()
    response = client.get(
        f"/projects/{project_id}/uploads/{uploaded['id']}/content"
    )
    assert response.status_code == 200
    assert response.content == content
    assert "text/plain" in response.headers["content-type"]
    assert "inline" in response.headers["content-disposition"]


def test_upload_content_404_for_other_project(client):
    project_a = _session(client)
    uploaded = client.post(
        f"/projects/{project_a}/uploads",
        files={"file": ("a.txt", b"secret", "text/plain")},
    ).json()
    project_b = client.post("/projects", json={"brief": "Other project"}).json()
    response = client.get(
        f"/projects/{project_b['id']}/uploads/{uploaded['id']}/content"
    )
    assert response.status_code == 404


def test_process_ingest_extracts_facts(client, db_session):
    project_id = _session(client)
    project = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    # .txt, not a Docling-covered extension (D71): keeps this test hermetic -
    # every Docling-covered format needs network + a gated HF token, tested
    # separately (mocked) in test_docling_parser.py.
    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project,
        account_id=account_id,
        filename="brief.txt",
        content_type="text/plain",
        body=b"Business need: reduce manual reporting. Risk: legacy ERP integration.",
        speaker_name="PM",
    )
    jobs = db_session.scalars(
        select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
    ).all()
    job = next(j for j in reversed(jobs) if j.payload.get("upload_id") == str(upload.id))
    assert job is not None
    ingestion_service.process_ingest_job(db_session, job)

    db_session.refresh(upload)
    assert upload.status == "done"
    chunks = db_session.scalars(
        select(EvidenceChunk).where(EvidenceChunk.upload_id == upload.id)
    ).all()
    assert len(chunks) >= 1
    cards = db_session.scalars(
        select(Card).where(Card.project_id == project.id, Card.kind != "source")
    ).all()
    assert len(cards) >= 1


def test_message_blocked_while_intake_pending(client):
    project_id = _session(client)
    client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("notes.txt", b"Stakeholders include the CFO.", "text/plain")},
    )
    # JOB_WORKER_ENABLED=false in tests (conftest.py) - the upload never
    # leaves "queued", so this reproduces the pre-processing race (D13 gap).
    response = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What's the budget?"},
    )
    assert response.status_code == 200
    messages = response.json()
    assert messages[-1]["role"] == "assistant"
    assert "still reading" in messages[-1]["content"].lower()
    # No interview turn ran: only the user's message and this reply exist.
    assert len(messages) == 2


def test_blocked_message_reshows_the_still_open_question(client):
    """Regression: a real answer sent while uploads are mid-processing must
    not silently vanish with no visible next step. The block reply should
    name what wasn't processed, and the still-open question (if any) must be
    re-shown - otherwise, once later messages push it out of the visible
    scrollback, the user has no way to tell what CrewLane is still waiting on
    even though the interview is correctly still waiting on it underneath."""
    project_id = _session(client)
    # Start the interview first (no intake pending yet) so a real question
    # is open before the upload below makes intake pending again.
    opened = client.get(f"/projects/{project_id}/messages").json()
    assert any(
        m.get("widget") and m["widget"].get("type") == "question_card" for m in opened
    )

    client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("notes.txt", b"Stakeholders include the CFO.", "text/plain")},
    )
    response = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "this answer must not be lost"},
    )
    assert response.status_code == 200
    messages = response.json()
    block_reply = next(m for m in messages if "still reading" in m["content"].lower())
    assert "this answer must not be lost" in block_reply["content"]
    assert messages[-1]["widget"]["type"] == "question_card"


def test_early_project_bypasses_relevance_gate(client, db_session):
    """A thin brief with no recorded facts yet has nothing to judge relevance
    against - the first uploads define the project, so every chunk is kept
    exactly like before this feature existed (D-junk-filter)."""
    project_id = _session(client)  # brief: "Upload test project" (<40 chars, no facts)
    project = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project,
        account_id=account_id,
        filename="anything.txt",
        content_type="text/plain",
        body=b"Completely unrelated content about baking bread.",
        speaker_name=None,
    )
    job = next(
        j
        for j in db_session.scalars(
            select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
        ).all()
        if j.payload.get("upload_id") == str(upload.id)
    )
    ingestion_service.process_ingest_job(db_session, job)

    db_session.refresh(upload)
    assert upload.status == "done"
    chunks = db_session.scalars(
        select(EvidenceChunk).where(EvidenceChunk.upload_id == upload.id)
    ).all()
    assert len(chunks) >= 1


def test_off_topic_upload_flagged_and_not_persisted(client, db_session):
    """Once the project has a real scope, an upload that shares no vocabulary
    with it is flagged instead of ingested, and nothing from it - no
    EvidenceChunk, no Card - lands in the database (D-junk-filter)."""
    client.post(
        "/auth/dev-session",
        json={"display_name": "Ingest", "email": "ingest2@example.com"},
    )
    project = client.post(
        "/projects",
        json={
            "brief": "Building a mobile banking app for small business customers "
            "with real-time fraud alerts and multi-factor authentication."
        },
    ).json()
    project_id = project["id"]
    project_row = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project_row,
        account_id=account_id,
        filename="recipe.txt",
        content_type="text/plain",
        body=b"Recipe for chocolate cake: mix flour sugar eggs and butter, "
        b"bake at 350 degrees for 40 minutes.",
        speaker_name=None,
    )
    job = next(
        j
        for j in db_session.scalars(
            select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
        ).all()
        if j.payload.get("upload_id") == str(upload.id)
    )
    ingestion_service.process_ingest_job(db_session, job)

    db_session.refresh(upload)
    assert upload.status == "flagged"
    assert upload.last_error

    chunks = db_session.scalars(
        select(EvidenceChunk).where(EvidenceChunk.upload_id == upload.id)
    ).all()
    assert chunks == []

    cards = db_session.scalars(
        select(Card).where(
            Card.project_id == project_row.id, Card.body.ilike("%chocolate%")
        )
    ).all()
    assert cards == []

    widgets = [
        m.widget
        for m in db_session.scalars(
            select(Message).where(
                Message.project_id == project_row.id, Message.role == "assistant"
            )
        ).all()
        if isinstance(m.widget, dict) and m.widget.get("type") == "off_topic_upload"
    ]
    assert len(widgets) == 1
    assert widgets[0]["upload_id"] == str(upload.id)


def test_keep_flagged_upload_ingests_previously_skipped_content(client, db_session):
    client.post(
        "/auth/dev-session",
        json={"display_name": "Ingest", "email": "ingest3@example.com"},
    )
    project = client.post(
        "/projects",
        json={"brief": "Building a mobile banking app with real-time fraud alerts."},
    ).json()
    project_id = project["id"]
    project_row = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project_row,
        account_id=account_id,
        filename="recipe.txt",
        content_type="text/plain",
        body=b"Recipe for chocolate cake: mix flour sugar eggs and butter.",
        speaker_name=None,
    )
    job = next(
        j
        for j in db_session.scalars(
            select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
        ).all()
        if j.payload.get("upload_id") == str(upload.id)
    )
    ingestion_service.process_ingest_job(db_session, job)
    db_session.refresh(upload)
    assert upload.status == "flagged"

    ingestion_service.keep_flagged_upload(db_session, project_row, upload)
    db_session.refresh(upload)
    assert upload.status == "done"
    assert upload.last_error is None
    chunks = db_session.scalars(
        select(EvidenceChunk).where(EvidenceChunk.upload_id == upload.id)
    ).all()
    assert len(chunks) >= 1


def test_discard_flagged_upload_stays_empty(client, db_session):
    client.post(
        "/auth/dev-session",
        json={"display_name": "Ingest", "email": "ingest4@example.com"},
    )
    project = client.post(
        "/projects",
        json={"brief": "Building a mobile banking app with real-time fraud alerts."},
    ).json()
    project_id = project["id"]
    project_row = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project_row,
        account_id=account_id,
        filename="recipe.txt",
        content_type="text/plain",
        body=b"Recipe for chocolate cake: mix flour sugar eggs and butter.",
        speaker_name=None,
    )
    job = next(
        j
        for j in db_session.scalars(
            select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
        ).all()
        if j.payload.get("upload_id") == str(upload.id)
    )
    ingestion_service.process_ingest_job(db_session, job)
    db_session.refresh(upload)
    assert upload.status == "flagged"

    ingestion_service.discard_flagged_upload(db_session, project_row, upload)
    db_session.refresh(upload)
    assert upload.status == "discarded"
    chunks = db_session.scalars(
        select(EvidenceChunk).where(EvidenceChunk.upload_id == upload.id)
    ).all()
    assert chunks == []


def test_message_blocked_with_actionable_text_while_only_flagged_upload_pending(
    client, db_session
):
    """Regression: has_pending_intake() blocks on a flagged upload (D86), but
    the old message only ever counted queued/processing uploads - with a
    flagged-only pending set that produced a nonsensical, permanently-stuck
    "Still reading 0 uploaded files" reply. The message must name the
    flagged upload and point at the keep/discard decision instead."""
    client.post(
        "/auth/dev-session",
        json={"display_name": "Ingest", "email": "ingest5@example.com"},
    )
    project = client.post(
        "/projects",
        json={"brief": "Building a mobile banking app with real-time fraud alerts."},
    ).json()
    project_id = project["id"]
    project_row = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project_row,
        account_id=account_id,
        filename="recipe.txt",
        content_type="text/plain",
        body=b"Recipe for chocolate cake: mix flour sugar eggs and butter.",
        speaker_name=None,
    )
    job = next(
        j
        for j in db_session.scalars(
            select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
        ).all()
        if j.payload.get("upload_id") == str(upload.id)
    )
    ingestion_service.process_ingest_job(db_session, job)
    db_session.refresh(upload)
    assert upload.status == "flagged"

    response = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "What's the budget?"},
    )
    assert response.status_code == 200
    reply = response.json()[-1]["content"].lower()
    assert "0 uploaded" not in reply
    assert "recipe.txt" in reply.lower() or "decision" in reply


def test_ingest_conflict_records_open_conflict(client, db_session):
    project_id = _session(client)
    project = db_session.get(Project, UUID(project_id))
    account_id = db_session.scalar(select(Account.id))

    upload = ingestion_service.enqueue_upload(
        db_session,
        project=project,
        account_id=account_id,
        filename="scope-a.txt",
        content_type="text/plain",
        body=b"Scope includes mobile apps for all caregivers.",
        speaker_name=None,
    )
    jobs = db_session.scalars(
        select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
    ).all()
    job = next(j for j in reversed(jobs) if j.payload.get("upload_id") == str(upload.id))
    ingestion_service.process_ingest_job(db_session, job)

    upload_b = ingestion_service.enqueue_upload(
        db_session,
        project=project,
        account_id=account_id,
        filename="scope-b.txt",
        content_type="text/plain",
        body=b"Scope excludes mobile apps entirely.",
        speaker_name=None,
    )
    jobs = db_session.scalars(
        select(Job).where(Job.kind == ingestion_service.INGEST_KIND)
    ).all()
    job_b = next(j for j in reversed(jobs) if j.payload.get("upload_id") == str(upload_b.id))
    ingestion_service.process_ingest_job(db_session, job_b)

    from app.services import belief as belief_service

    open_conflicts = belief_service.list_conflicts(db_session, project)
    assert len(open_conflicts) >= 1

    conflict_widgets = [
        m.widget
        for m in db_session.scalars(
            select(Message).where(Message.project_id == project.id, Message.role == "assistant")
        ).all()
        if isinstance(m.widget, dict) and m.widget.get("type") == "conflict_card"
    ]
    assert conflict_widgets == []
