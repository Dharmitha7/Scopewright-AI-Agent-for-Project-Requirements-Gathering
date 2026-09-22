from unittest.mock import patch
from uuid import UUID

from sqlalchemy import func, select

from app.models.job import Job
from app.models.upload import Upload
from app.services.transcription import MAX_TRANSCRIBE_BYTES


def _session(client):
    client.post(
        "/auth/dev-session",
        json={"display_name": "Transcribe", "email": "transcribe@example.com"},
    )
    project = client.post("/projects", json={"brief": "Dictation test project"}).json()
    return project["id"]


@patch("app.routers.projects.transcribe_audio", return_value="Hello from the mic.")
def test_transcribe_returns_text_without_ingest(mock_transcribe, client, db_session):
    project_id = _session(client)
    pid = UUID(project_id)
    uploads_before = db_session.scalar(
        select(func.count()).select_from(Upload).where(Upload.project_id == pid)
    )
    jobs_before = db_session.scalar(select(func.count()).select_from(Job))
    response = client.post(
        f"/projects/{project_id}/transcribe",
        files={"file": ("dictation.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json() == {"text": "Hello from the mic."}
    mock_transcribe.assert_called_once()
    uploads_after = db_session.scalar(
        select(func.count()).select_from(Upload).where(Upload.project_id == pid)
    )
    jobs_after = db_session.scalar(select(func.count()).select_from(Job))
    assert uploads_after == uploads_before
    assert jobs_after == jobs_before


def test_transcribe_rejects_non_audio(client):
    project_id = _session(client)
    response = client.post(
        f"/projects/{project_id}/transcribe",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "audio file required"


def test_transcribe_rejects_oversized_recording(client):
    project_id = _session(client)
    response = client.post(
        f"/projects/{project_id}/transcribe",
        files={
            "file": (
                "dictation.webm",
                b"x" * (MAX_TRANSCRIBE_BYTES + 1),
                "audio/webm",
            )
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "recording too large"
