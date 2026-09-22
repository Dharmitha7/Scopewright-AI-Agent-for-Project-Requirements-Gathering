"""Project create/list. The user names the project; when they don't, the AI
suggests a name from the brief (stop-1 decision, 2026-08-19)."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents.inference import PURPOSE_TAG, get_inference
from app.core.config import get_settings
from app.models.account import Account
from app.models.audit_event import AuditEvent
from app.models.card import Card
from app.models.evidence_chunk import EvidenceChunk
from app.models.job import Job
from app.models.message import Message
from app.models.project import Project
from app.models.retrieval_trace import RetrievalTraceEvent
from app.models.snapshot import Snapshot
from app.models.string import CardString
from app.models.upload import Upload
from app.services import ingestion as ingestion_service


def derive_project_name(brief: str) -> str:
    words = brief.strip().split()
    name = " ".join(words[:6]) or "Untitled project"
    return name[:120]


def suggest_project_name(brief: str) -> str:
    settings = get_settings()
    raw = get_inference(settings).complete(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": (
                    f"{PURPOSE_TAG} name\n"
                    "Suggest a short 2-5 word working name for this software "
                    "project. Plain text only: no quotes, no punctuation, "
                    "no explanation."
                ),
            },
            {"role": "user", "content": brief[:2000]},
        ],
    )
    name = (raw.strip().strip('"').splitlines() or [""])[0].strip()
    return name[:120] or derive_project_name(brief)


def get_account(session: Session, account_id: UUID) -> Account | None:
    return session.get(Account, account_id)


def upsert_dev_account(session: Session, *, email: str, display_name: str) -> Account:
    account = session.scalar(select(Account).where(Account.email == email))
    if account is None:
        account = Account(
            email=email,
            display_name=display_name,
            provider_id=f"dev:{email}",
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        return account
    account.display_name = display_name
    session.commit()
    session.refresh(account)
    return account


def list_projects(session: Session, account_id: UUID) -> list[Project]:
    return list(
        session.scalars(
            select(Project)
            .where(Project.created_by_account_id == account_id)
            .order_by(Project.created_at.desc())
        ).all()
    )


def create_project(
    session: Session, account_id: UUID, brief: str, *, name: str | None = None
) -> Project:
    clean_name = (name or "").strip()[:120]
    project = Project(
        name=clean_name or suggest_project_name(brief),
        brief=brief.strip(),
        created_by_account_id=account_id,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    # The AI reads the brief before it ever asks a question.
    ingestion_service.mine_brief(session, project)
    return project


def get_project(session: Session, account_id: UUID, project_id: UUID) -> Project | None:
    return session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.created_by_account_id == account_id,
        )
    )


def rename_project(session: Session, project: Project, name: str) -> Project:
    project.name = name.strip()[:120]
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project: Project) -> None:
    """Remove project and all owned rows (no FK cascades in schema)."""
    pid = project.id
    for job in session.scalars(select(Job)).all():
        if str((job.payload or {}).get("project_id") or "") == str(pid):
            session.delete(job)
    session.execute(delete(CardString).where(CardString.project_id == pid))
    session.execute(delete(EvidenceChunk).where(EvidenceChunk.project_id == pid))
    session.execute(delete(Message).where(Message.project_id == pid))
    session.execute(delete(Card).where(Card.project_id == pid))
    session.execute(delete(Upload).where(Upload.project_id == pid))
    session.execute(delete(Snapshot).where(Snapshot.project_id == pid))
    session.execute(delete(AuditEvent).where(AuditEvent.project_id == pid))
    session.execute(delete(RetrievalTraceEvent).where(RetrievalTraceEvent.project_id == pid))
    session.delete(project)
    session.commit()
