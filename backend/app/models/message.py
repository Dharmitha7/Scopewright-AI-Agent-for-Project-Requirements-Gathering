"""Chat spine messages (D10). Trusted catalog widget: question_card."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("project_id", "seq"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    widget: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="planning")
    thread_key: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def max_seq(session: Session, project_id: UUID) -> int:
    """Highest message seq in a project (0 when empty)."""
    return (
        session.scalar(
            select(Message.seq)
            .where(Message.project_id == project_id)
            .order_by(Message.seq.desc())
            .limit(1)
        )
        or 0
    )
