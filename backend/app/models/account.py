"""Account — D5 JIT, D6 stored identity (name, email, provider ID)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    provider_id: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    # Personal OneDrive OAuth (D85) — refresh token for the project creator's drive.
    ms_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    ms_drive_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ms_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
