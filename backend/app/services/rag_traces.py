from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.retrieval_trace import RetrievalTraceEvent


def record(session: Session, *, project_id: UUID, kind: str, query: str, detail: dict) -> None:
    session.add(RetrievalTraceEvent(project_id=project_id, kind=kind, query=query, detail=detail))
    session.commit()


def list_traces(session: Session, project_id: UUID, *, limit: int = 100) -> list[dict]:
    rows = session.scalars(
        select(RetrievalTraceEvent)
        .where(RetrievalTraceEvent.project_id == project_id)
        .order_by(RetrievalTraceEvent.created_at.desc())
        .limit(min(max(limit, 1), 500))
    ).all()
    return [
        {
            "id": str(row.id),
            "kind": row.kind,
            "query": row.query,
            "detail": row.detail,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
