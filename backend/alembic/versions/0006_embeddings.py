"""card and evidence_chunk embeddings

Revision ID: 0006_embeddings
Revises: 0005_uploads_evidence
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_embeddings"
down_revision: Union[str, Sequence[str], None] = "0005_uploads_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    json_type = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")
    op.add_column("cards", sa.Column("embedding", json_type, nullable=True))
    op.add_column("evidence_chunks", sa.Column("embedding", json_type, nullable=True))


def downgrade() -> None:
    op.drop_column("evidence_chunks", "embedding")
    op.drop_column("cards", "embedding")
