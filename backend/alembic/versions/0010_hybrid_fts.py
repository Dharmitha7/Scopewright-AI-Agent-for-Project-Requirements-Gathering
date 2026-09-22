"""hybrid keyword search: generated tsvector + GIN index on card/chunk body

Revision ID: 0010_hybrid_fts
Revises: 0009_pgvector_embeddings
"""

from alembic import op

revision = "0010_hybrid_fts"
down_revision = "0009_pgvector_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # No sqlite equivalent for tsvector/FTS. The keyword-search path
        # (retrieval.py's _sql_keyword_matches_*) only ever runs when
        # _supports_pgvector() is True, so sqlite's test schema simply never
        # needs this column - same "Postgres-only, no-op elsewhere" shape
        # as migration 0009.
        return

    # 'simple' over 'english': this lane exists specifically to catch exact
    # product/company names ("Stripe", "Mindbody") and bare numbers ("70%"),
    # and English stemming/stopword removal works against that (it can fold
    # a proper noun through the stemmer, or drop a short token as a
    # stopword) - see DECISIONS.md D66.
    op.execute(
        """
        ALTER TABLE cards
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(body, ''))) STORED
        """
    )
    op.create_index(
        "ix_cards_search_vector",
        "cards",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.execute(
        """
        ALTER TABLE evidence_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(body, ''))) STORED
        """
    )
    op.create_index(
        "ix_evidence_chunks_search_vector",
        "evidence_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.drop_index("ix_evidence_chunks_search_vector", table_name="evidence_chunks")
    op.drop_column("evidence_chunks", "search_vector")
    op.drop_index("ix_cards_search_vector", table_name="cards")
    op.drop_column("cards", "search_vector")
