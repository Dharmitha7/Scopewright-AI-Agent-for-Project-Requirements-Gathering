"""OneDrive local-mirror sync (D85) — branded PDF publish."""

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.models.job import Job
from app.models.project import Project
from app.services import onedrive as onedrive_service


def test_sanitize_and_pack_filename() -> None:
    assert ":" not in onedrive_service.sanitize_folder_name('Clinic: "A/B"')
    name = onedrive_service.pack_filename("requirements_summary", "Requirements Summary")
    assert name.endswith(".pdf")
    project = SimpleNamespace(name="Charge Spot Finder")
    assert onedrive_service.project_root_name(project) == "CrewLane/Charge Spot Finder"


def test_local_mirror_writes_tree(
    tmp_path: Path, client: TestClient, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("ONEDRIVE_LOCAL_MIRROR_DIR", str(tmp_path))
    get_settings.cache_clear()

    client.post("/auth/dev-session", json={"display_name": "OD", "email": "od@example.com"})
    project = client.post(
        "/projects",
        json={"brief": "Clinic portal for patients", "name": "Clinic Portal"},
    ).json()
    project_id = UUID(project["id"])
    row = db_session.get(Project, project_id)
    assert row is not None

    onedrive_service.sync_planning_final(db_session, row, 1, "# Charter\n\n## Purpose\n\nBody")
    onedrive_service.sync_requirements_draft(
        db_session,
        row,
        {"requirements_summary": "# Summary\n\nDraft"},
    )
    dirty = (
        "<!-- crewlane:draft-changelog -->\n## Changes\n- x\n"
        "<!-- /crewlane:draft-changelog -->\n\n# Summary\n\nFinal"
    )
    onedrive_service.sync_requirements_final(
        db_session,
        row,
        2,
        {"requirements_summary": dirty},
    )

    jobs = list(
        db_session.scalars(select(Job).where(Job.kind == onedrive_service.ONEDRIVE_SYNC_KIND))
    )
    mine = [j for j in jobs if j.payload.get("project_id") == str(project_id)]
    assert len(mine) == 3
    for job in mine:
        onedrive_service.process_onedrive_job(db_session, job)
        assert job.status == "done"

    root = tmp_path / "CrewLane" / "Clinic Portal"
    charter = root / "planning" / "final" / "v1" / "Project-Charter.pdf"
    draft = root / "requirements" / "draft" / "Requirements-Summary.pdf"
    final = root / "requirements" / "final" / "v2" / "Requirements-Summary.pdf"
    assert charter.read_bytes()[:5] == b"%PDF-"
    assert draft.read_bytes()[:5] == b"%PDF-"
    final_bytes = final.read_bytes()
    assert final_bytes[:5] == b"%PDF-"
    assert len(final_bytes) > 5000
    assert b"crewlane:draft-changelog" not in final_bytes

    get_settings.cache_clear()


def test_skips_when_onedrive_not_connected(db_session, monkeypatch) -> None:
    monkeypatch.delenv("ONEDRIVE_LOCAL_MIRROR_DIR", raising=False)
    get_settings.cache_clear()

    from app.models.account import Account

    owner = Account(display_name="OD", email="skip@example.com")
    db_session.add(owner)
    db_session.flush()
    project = Project(
        name="No Drive",
        brief="x",
        phase="planning",
        created_by_account_id=owner.id,
    )
    db_session.add(project)
    db_session.commit()

    onedrive_service.sync_planning_final(db_session, project, 1, "# Charter\n\nBody")
    job = db_session.scalars(
        select(Job).where(Job.kind == onedrive_service.ONEDRIVE_SYNC_KIND)
    ).first()
    assert job is not None
    onedrive_service.process_onedrive_job(db_session, job)
    assert job.status == "done"
    assert job.last_error == "onedrive not connected; skipped"

    get_settings.cache_clear()


def test_process_job_errors_on_unknown_sync(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEDRIVE_LOCAL_MIRROR_DIR", str(tmp_path))
    get_settings.cache_clear()

    from app.models.account import Account

    owner = Account(display_name="OD", email="bad@example.com")
    db_session.add(owner)
    db_session.flush()
    project = Project(name="P", brief="x", phase="planning", created_by_account_id=owner.id)
    db_session.add(project)
    db_session.commit()
    job = Job(
        kind=onedrive_service.ONEDRIVE_SYNC_KIND,
        payload={"project_id": str(project.id), "sync": "nope"},
        status="queued",
    )
    db_session.add(job)
    db_session.commit()

    try:
        onedrive_service.process_onedrive_job(db_session, job)
    except ValueError as exc:
        assert "unknown onedrive sync kind" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    get_settings.cache_clear()
