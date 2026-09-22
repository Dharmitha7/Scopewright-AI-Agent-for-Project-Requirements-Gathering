"""Project — D9 one free-text brief; name is derived. Creator only, not membership."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    # Lifecycle pointer (D45): which phase's thread owns the conversation now.
    phase: Mapped[str] = mapped_column(String(32), nullable=False, server_default="planning")
    # D83: incremented on each Accept for that phase's final OneDrive folder vN.0.
    planning_doc_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requirements_doc_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Bidirectional editing (D89): true while an already-accepted Planning is
    # reopened for a targeted redraft. project.phase stays on "requirements"/
    # "done" throughout - this flag, not phase, is what makes the Planning
    # tab writable again during that window.
    planning_redraft_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    # Cached Graph/local folder ids for OneDrive tree (D85).
    onedrive_folders: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
