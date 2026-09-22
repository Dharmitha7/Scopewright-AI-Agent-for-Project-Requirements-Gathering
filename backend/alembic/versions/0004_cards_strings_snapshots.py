"""cards, strings, snapshots

Revision ID: 0004_cards_strings_snapshots
Revises: 0003_project_phase
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_cards_strings_snapshots"
down_revision: Union[str, Sequence[str], None] = "0003_project_phase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("coverage_area", sa.String(length=64), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cards_project_id", "cards", ["project_id"])
    op.create_index("ix_cards_coverage_area", "cards", ["coverage_area"])

    op.create_table(
        "strings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("from_card_id", sa.Uuid(), nullable=False),
        sa.Column("to_card_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["from_card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["to_card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strings_project_id", "strings", ["project_id"])
    op.create_index("ix_strings_from_card_id", "strings", ["from_card_id"])
    op.create_index("ix_strings_to_card_id", "strings", ["to_card_id"])

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("card_versions", sa.JSON(), nullable=False),
        sa.Column("accepted_by_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["accepted_by_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snapshots_project_id", "snapshots", ["project_id"])


def downgrade() -> None:
    op.drop_table("snapshots")
    op.drop_table("strings")
    op.drop_table("cards")
