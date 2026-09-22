"""Planning redraft flag for bidirectional Planning <-> Requirements editing (D89).

Revision ID: 0016_planning_redraft_active
Revises: 0015_messages_phase
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_planning_redraft_active"
down_revision = "0015_messages_phase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "planning_redraft_active", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "planning_redraft_active")
