"""Doc versions + Microsoft OneDrive connection fields (D83/D85).

Revision ID: 0014_doc_versions_onedrive
Revises: 0013_exact_channel_trgm_index
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_doc_versions_onedrive"
down_revision = "0013_exact_channel_trgm_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("planning_doc_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "projects",
        sa.Column("requirements_doc_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "projects",
        sa.Column("onedrive_folders", sa.JSON(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("ms_refresh_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("ms_drive_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("ms_connected_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "ms_connected_at")
    op.drop_column("accounts", "ms_drive_id")
    op.drop_column("accounts", "ms_refresh_token")
    op.drop_column("projects", "onedrive_folders")
    op.drop_column("projects", "requirements_doc_version")
    op.drop_column("projects", "planning_doc_version")
