"""CardString - the 4 D22 edge kinds: supported-by, derived-from, depends-on,
conflicts-with. v1 only writes supported-by (fact card -> its source card).

Named CardString, not String, because every model module in this package
imports sqlalchemy.String for column types - naming the class String would
shadow it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CardString(Base):
    __tablename__ = "strings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    from_card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)
    to_card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
