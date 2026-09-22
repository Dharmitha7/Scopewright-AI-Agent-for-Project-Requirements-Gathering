"""Stamp messages with phase and thread_key for Planning/Requirements tabs.

Revision ID: 0015_messages_phase
Revises: 0014_doc_versions_onedrive

Backfill heuristic: if the project is still in planning, every row is planning.
Otherwise rows created at or before the first planning snapshot's created_at
are planning; later rows are requirements on the current requirements thread.
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_messages_phase"
down_revision = "0014_doc_versions_onedrive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("phase", sa.String(length=32), nullable=False, server_default="planning"),
    )
    op.add_column(
        "messages",
        sa.Column("thread_key", sa.String(length=120), nullable=False, server_default=""),
    )
    conn = op.get_bind()
    projects = conn.execute(sa.text("SELECT id, phase, requirements_doc_version FROM projects")).fetchall()
    for project_id, phase, req_ver in projects:
        pid = str(project_id)
        planning_key = f"{pid}:planning"
        req_key = f"{pid}:requirements:v{int(req_ver or 0)}"
        if phase == "planning":
            conn.execute(
                sa.text(
                    "UPDATE messages SET phase = 'planning', thread_key = :tk "
                    "WHERE project_id = :pid"
                ),
                {"tk": planning_key, "pid": project_id},
            )
            continue
        first_plan = conn.execute(
            sa.text(
                "SELECT created_at FROM snapshots WHERE project_id = :pid AND phase = 'planning' "
                "ORDER BY created_at ASC LIMIT 1"
            ),
            {"pid": project_id},
        ).fetchone()
        cutoff = first_plan[0] if first_plan else None
        if cutoff is None:
            conn.execute(
                sa.text(
                    "UPDATE messages SET phase = 'requirements', thread_key = :tk "
                    "WHERE project_id = :pid"
                ),
                {"tk": req_key, "pid": project_id},
            )
            continue
        conn.execute(
            sa.text(
                "UPDATE messages SET phase = 'planning', thread_key = :tk "
                "WHERE project_id = :pid AND created_at <= :cutoff"
            ),
            {"tk": planning_key, "pid": project_id, "cutoff": cutoff},
        )
        conn.execute(
            sa.text(
                "UPDATE messages SET phase = 'requirements', thread_key = :tk "
                "WHERE project_id = :pid AND created_at > :cutoff"
            ),
            {"tk": req_key, "pid": project_id, "cutoff": cutoff},
        )
    op.alter_column("messages", "phase", server_default=None)
    op.alter_column("messages", "thread_key", server_default=None)


def downgrade() -> None:
    op.drop_column("messages", "thread_key")
    op.drop_column("messages", "phase")
