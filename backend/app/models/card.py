"""Card - D22 typed knowledge graph node. Status: candidate -> confirmed -> accepted.

`kind` holds one of the 15 D22 kinds (see DECISIONS.md D22); v1
only ever writes a subset. No DB-level CHECK constraint, matching the rest of
this schema (e.g. Job.status, GateActionIn.action) - kinds are validated in
Python, not SQL.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.embedding_config import EMBEDDING_DIMENSIONS
from app.models.base import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # Template coverage-area key (templates.py); null for area-less kinds (source).
    coverage_area: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Real pgvector column on Postgres (HNSW-indexed, migration 0009); a plain
    # JSON column on sqlite (tests) since Vector has no sqlite equivalent -
    # same with_variant idiom used everywhere else in this schema, base/variant
    # roles swapped.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
