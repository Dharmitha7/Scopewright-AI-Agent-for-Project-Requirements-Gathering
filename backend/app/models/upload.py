"""Uploaded evidence file (D13). Raw bytes live in object storage; rows track provenance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    submitted_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False
    )
    # Dual provenance (D13): who uploaded vs who spoke (optional for documents).
    speaker_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # queued -> processing -> done | failed | flagged -> done | discarded.
    # "flagged": every chunk was judged off-topic for this project during
    # ingestion (junk-upload filtering) - nothing was persisted from it, and
    # it awaits a human keep/discard decision (see ingestion_service).
    # "discarded": the human confirmed a flagged upload should stay excluded.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
