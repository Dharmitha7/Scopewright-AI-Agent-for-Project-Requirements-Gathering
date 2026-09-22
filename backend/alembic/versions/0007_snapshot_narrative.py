"""snapshot narrative document

Revision ID: 0007_snapshot_narrative
Revises: 0006_embeddings
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_snapshot_narrative"
down_revision: Union[str, Sequence[str], None] = "0006_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("snapshots", sa.Column("narrative", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("snapshots", "narrative")
