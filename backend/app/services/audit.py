"""Audit trail writes/reads. One insert per human decision; never updated."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit_event import AuditEvent


def record(
    session: Session,
    *,
    project_id: UUID,
    account_id: UUID,
    kind: str,
    detail: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            project_id=project_id,
            account_id=account_id,
            kind=kind,
            detail=detail or {},
        )
    )
    session.commit()


def list_events(session: Session, project_id: UUID) -> list[dict]:
    rows = session.execute(
        select(AuditEvent, Account.display_name)
        .join(Account, Account.id == AuditEvent.account_id)
        .where(AuditEvent.project_id == project_id)
        .order_by(AuditEvent.created_at.desc())
    ).all()
    return [
        {
            "id": str(event.id),
            "kind": event.kind,
            "actor": display_name,
            "detail": event.detail,
            "created_at": event.created_at.isoformat(),
        }
        for event, display_name in rows
    ]
