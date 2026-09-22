"""Snapshot - immutable pointer set frozen at gate accept (D17/D20).

card_versions is a JSON array of {"card_id": str, "version": int} pointers -
not a prose blob and not a stored document (rethink/D17 preference). The
document view itself is rendered from those pointers later (Rahul's next
branch), not stored here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    card_versions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    accepted_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False
    )
    # LLM-composed narrative view generated at gate accept (D60); the audit
    # view stays deterministic from card_versions.
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Selectable deliverable packs (D70): {"mode": "combined"|"separate",
    # "packs": {pack_key: markdown}, "combined": markdown|null}.
    narratives: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
