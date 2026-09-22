"""project phase pointer

Revision ID: 0003_project_phase
Revises: 0002_messages
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_project_phase"
down_revision: Union[str, Sequence[str], None] = "0002_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("phase", sa.String(length=32), nullable=False, server_default="planning"),
    )


def downgrade() -> None:
    op.drop_column("projects", "phase")
