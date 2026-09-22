"""OneDrive (or local mirror) publish path for branded PDFs (D85)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.account import Account
from app.models.job import Job
from app.models.project import Project
from app.services.document_export import build_publish_meta, export_branded_pdf
from app.services.draft_changelog import strip_changelog

log = logging.getLogger(__name__)

ONEDRIVE_SYNC_KIND = "onedrive_sync"
DRIVE_APP_FOLDER = "CrewLane"
PDF_CONTENT_TYPE = "application/pdf"


def sanitize_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip() or "CrewLane-Project"
    return cleaned[:120]


def pack_filename(pack_key: str, title: str | None = None, *, ext: str = "pdf") -> str:
    # Same forbidden-character set as sanitize_folder_name() above - a pack
    # title like "Epics -> Features -> Stories" otherwise reaches Graph with
    # a literal ">" and gets rejected outright with 400 Bad Request.
    base = re.sub(r'[<>:"/\\|?*]', "", (title or pack_key))
    base = re.sub(r"\s+", "-", base.strip()) or pack_key
    return f"{base}.{ext.lstrip('.')}"


class DriveWriter(Protocol):
    def put_bytes(self, relative_path: str, content: bytes, *, content_type: str) -> None: ...

    def clear_prefix(self, relative_prefix: str) -> None: ...


class LocalMirrorWriter:
    """Writes the same tree under a local directory (tests / offline demo)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, relative_path: str, content: bytes, *, content_type: str) -> None:
        del content_type
        path = self._root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def clear_prefix(self, relative_prefix: str) -> None:
        folder = self._root / relative_prefix
        if not folder.exists():
            return
        for child in folder.iterdir():
            if child.is_file():
                child.unlink()


class GraphDriveWriter:
    """Minimal Graph upload to the signed-in user's personal drive."""

    def __init__(self, *, access_token: str, drive_id: str = "me") -> None:
        self._token = access_token
        self._drive = drive_id

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def put_bytes(self, relative_path: str, content: bytes, *, content_type: str) -> None:
        path = relative_path.replace("\\", "/").lstrip("/")
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded}:/content"
        response = httpx.put(
            url,
            headers={**self._headers(), "Content-Type": content_type},
            content=content,
            timeout=60.0,
        )
        response.raise_for_status()

    def clear_prefix(self, relative_prefix: str) -> None:
        path = relative_prefix.replace("\\", "/").rstrip("/")
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        list_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded}:/children"
        try:
            listed = httpx.get(list_url, headers=self._headers(), timeout=30.0)
            if listed.status_code == 404:
                return
            listed.raise_for_status()
            for item in listed.json().get("value") or []:
                item_id = item.get("id")
                if not item_id:
                    continue
                httpx.delete(
                    f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}",
                    headers=self._headers(),
                    timeout=30.0,
                ).raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("onedrive clear_prefix failed for %s: %s", path, exc)


def _writer_for_owner(settings: Settings, owner: Account) -> DriveWriter | None:
    if settings.onedrive_local_mirror_dir:
        return LocalMirrorWriter(Path(settings.onedrive_local_mirror_dir))
    if not owner.ms_refresh_token or not settings.microsoft_client_id:
        return None
    token = refresh_access_token(settings, owner.ms_refresh_token)
    return GraphDriveWriter(access_token=token, drive_id=owner.ms_drive_id or "me")


def refresh_access_token(settings: Settings, refresh_token: str) -> str:
    data = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": "offline_access Files.ReadWrite User.Read",
    }
    token_url = (
        f"https://login.microsoftonline.com/{settings.microsoft_tenant}/oauth2/v2.0/token"
    )
    response = httpx.post(token_url, data=data, timeout=30.0)
    response.raise_for_status()
    return str(response.json()["access_token"])


def project_root_name(project: Project) -> str:
    """/{CrewLane}/{ProjectName}/… so projects are not dumped at drive root."""
    return f"{DRIVE_APP_FOLDER}/{sanitize_folder_name(project.name)}"


def enqueue_sync(
    session: Session,
    *,
    project_id: UUID,
    kind: str,
    payload: dict,
) -> None:
    """Queue OneDrive work; never blocks Accept/Generate (D85)."""
    session.add(
        Job(
            kind=ONEDRIVE_SYNC_KIND,
            payload={"project_id": str(project_id), "sync": kind, **payload},
            status="queued",
        )
    )
    session.commit()


def _branded_pdf(
    project: Project,
    *,
    phase: str,
    version: int,
    markdown: str,
    pack_key: str | None = None,
    strip_draft_changelog: bool = False,
) -> bytes:
    body = strip_changelog(markdown) if strip_draft_changelog else markdown
    meta = build_publish_meta(project, phase=phase, version=version, pack_key=pack_key)
    return export_branded_pdf(body, meta)


def _put_pdf(
    writer: DriveWriter,
    relative_path: str,
    project: Project,
    *,
    phase: str,
    version: int,
    markdown: str,
    pack_key: str | None = None,
    strip_draft_changelog: bool = False,
) -> None:
    pdf = _branded_pdf(
        project,
        phase=phase,
        version=version,
        markdown=markdown,
        pack_key=pack_key,
        strip_draft_changelog=strip_draft_changelog,
    )
    writer.put_bytes(relative_path, pdf, content_type=PDF_CONTENT_TYPE)


def sync_planning_draft(
    session: Session, project: Project, version: int, markdown: str
) -> None:
    enqueue_sync(
        session,
        project_id=project.id,
        kind="planning_draft",
        payload={"version": version, "markdown": markdown},
    )


def sync_planning_final(session: Session, project: Project, version: int, markdown: str) -> None:
    enqueue_sync(
        session,
        project_id=project.id,
        kind="planning_final",
        payload={"version": version, "markdown": strip_changelog(markdown)},
    )


def sync_requirements_draft(
    session: Session, project: Project, packs: dict[str, str]
) -> None:
    version = int(project.requirements_doc_version or 0) + 1
    enqueue_sync(
        session,
        project_id=project.id,
        kind="requirements_draft",
        payload={"version": version, "packs": packs},
    )


def sync_requirements_final(
    session: Session, project: Project, version: int, packs: dict[str, str]
) -> None:
    clean = {k: strip_changelog(v) for k, v in packs.items()}
    enqueue_sync(
        session,
        project_id=project.id,
        kind="requirements_final",
        payload={"version": version, "packs": clean},
    )


def process_onedrive_job(session: Session, job: Job) -> None:
    settings = get_settings()
    project_id = UUID(str(job.payload["project_id"]))
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("project missing")
    owner = session.get(Account, project.created_by_account_id)
    if owner is None:
        raise ValueError("owner missing")

    writer = _writer_for_owner(settings, owner)
    if writer is None:
        job.status = "done"
        job.last_error = "onedrive not connected; skipped"
        session.commit()
        return

    root = project_root_name(project)
    sync = str(job.payload.get("sync") or "")
    from app.agents.deliverables import PACK_BY_KEY

    if sync == "planning_draft":
        ver = int(job.payload["version"])
        _put_pdf(
            writer,
            f"{root}/planning/draft/Project-Charter.pdf",
            project,
            phase="planning",
            version=ver,
            markdown=str(job.payload.get("markdown") or ""),
            strip_draft_changelog=True,
        )
    elif sync == "planning_final":
        ver = int(job.payload["version"])
        _put_pdf(
            writer,
            f"{root}/planning/final/v{ver}/Project-Charter.pdf",
            project,
            phase="planning",
            version=ver,
            markdown=str(job.payload.get("markdown") or ""),
            strip_draft_changelog=True,
        )
    elif sync == "requirements_draft":
        writer.clear_prefix(f"{root}/requirements/draft")
        ver = int(job.payload["version"])
        packs = dict(job.payload.get("packs") or {})
        for key, body in packs.items():
            title = PACK_BY_KEY[key].title if key in PACK_BY_KEY else key
            _put_pdf(
                writer,
                f"{root}/requirements/draft/{pack_filename(key, title)}",
                project,
                phase="requirements",
                version=ver,
                markdown=body,
                pack_key=key,
            )
    elif sync == "requirements_final":
        ver = int(job.payload["version"])
        packs = dict(job.payload.get("packs") or {})
        for key, body in packs.items():
            title = PACK_BY_KEY[key].title if key in PACK_BY_KEY else key
            _put_pdf(
                writer,
                f"{root}/requirements/final/v{ver}/{pack_filename(key, title)}",
                project,
                phase="requirements",
                version=ver,
                markdown=body,
                pack_key=key,
                strip_draft_changelog=True,
            )
    else:
        raise ValueError(f"unknown onedrive sync kind: {sync}")

    job.status = "done"
    job.last_error = None
    session.commit()
