"""snapshot pack narratives JSON (selectable deliverables)

Revision ID: 0011_snapshot_narratives
Revises: 0010_hybrid_fts
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_snapshot_narratives"
down_revision = "0010_hybrid_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column(
            "narratives",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("snapshots", "narratives")
