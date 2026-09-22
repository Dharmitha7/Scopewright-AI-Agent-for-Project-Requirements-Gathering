"""Audit event - one row per human decision or interview answer (NFR-3).

The AI's own work is traceable through cards/strings/snapshots; this table
records what PEOPLE did: created, answered, skipped, uploaded, edited, struck,
resolved, accepted, revised. Rows are only ever inserted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    # Python-side default: microsecond precision keeps ordering deterministic
    # on sqlite, where server-side now() is second-granular.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
