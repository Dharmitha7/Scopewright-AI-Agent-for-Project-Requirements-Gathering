"""machine retrieval traces

Revision ID: 0012_retrieval_traces
Revises: 0011_snapshot_narratives
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_retrieval_traces"
down_revision: Union[str, Sequence[str], None] = "0011_snapshot_narratives"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retrieval_traces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_traces_project_id", "retrieval_traces", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_traces_project_id", table_name="retrieval_traces")
    op.drop_table("retrieval_traces")
