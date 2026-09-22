"""trigram GIN index for the exact-match retrieval channel

Revision ID: 0013_exact_channel_trgm_index
Revises: 0012_retrieval_traces
"""

from alembic import op

revision = "0013_exact_channel_trgm_index"
down_revision = "0012_retrieval_traces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # No sqlite equivalent for pg_trgm/GIN - retrieval.py's exact channel
        # only ever runs when _supports_pgvector() is True, same "Postgres-
        # only, no-op elsewhere" shape as migrations 0009/0010.
        return

    # retrieval.py's _exact_channel() does `lower(body) LIKE '%term%'` across
    # up to 12 terms, over both tables, unindexed - fine on a handful of rows
    # (the eval corpus), but a sequential scan that gets slower as every
    # project's evidence grows. A trigram GIN index gives Postgres an index
    # path for that exact LIKE '%...%' pattern instead of a full scan.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_cards_body_trgm ON cards USING gin (lower(body) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_evidence_chunks_body_trgm "
        "ON evidence_chunks USING gin (lower(body) gin_trgm_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.drop_index("ix_evidence_chunks_body_trgm", table_name="evidence_chunks")
    op.drop_index("ix_cards_body_trgm", table_name="cards")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
