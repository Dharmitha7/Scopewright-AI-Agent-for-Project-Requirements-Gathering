"""chat messages

Revision ID: 0002_messages
Revises: 0001_accounts_projects
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_messages"
down_revision: Union[str, Sequence[str], None] = "0001_accounts_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("widget", sa.JSON(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_project_id", "messages", ["project_id"])
    op.create_index("ix_messages_project_id_seq", "messages", ["project_id", "seq"], unique=True)


def downgrade() -> None:
    op.drop_table("messages")
