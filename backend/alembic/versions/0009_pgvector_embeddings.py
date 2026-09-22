"""real pgvector Vector column for card/evidence_chunk embeddings

Revision ID: 0009_pgvector_embeddings
Revises: 0008_audit_events
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0009_pgvector_embeddings"
down_revision = "0008_audit_events"
branch_labels = None
depends_on = None

# Literal, not imported from app.core.embedding_config: no migration in this
# repo imports app.* (migrations are self-contained snapshots that must stay
# reproducible even after the "current" constant changes later).
EMBEDDING_DIM = 768


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # sqlite's test schema comes from Base.metadata.create_all() via the
        # ORM's Vector(...).with_variant(JSON(), "sqlite"), never from here.
        return

    # ACKNOWLEDGED TRADEOFF: existing JSON/JSONB embedding values (if any)
    # cannot be reinterpreted as vector(768) - no implicit cast, and they were
    # produced (if ever populated) at whatever Gemini's un-set-dimensionality
    # default was (~3072), not 768. Every environment observed while designing
    # this (local .env, docker-compose.yml, conftest.py) has no
    # GEMINI_API_KEY set anywhere, so this column is NULL in practice
    # everywhere today - treated as a clean type change, not a
    # value-preserving one. A real deployment with populated legacy
    # embeddings would need to re-embed (re-run ingestion / re-save cards)
    # after upgrading; there is no automatic backfill here.
    op.drop_column("cards", "embedding")
    op.drop_column("evidence_chunks", "embedding")
    op.add_column("cards", sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True))
    op.add_column(
        "evidence_chunks", sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True)
    )

    # HNSW over IVFFlat: IVFFlat needs a `lists` parameter tuned to expected
    # final row count and degrades (needing a rebuild) as data grows past
    # that; this system's cards/chunks grow incrementally per interview turn
    # with no bulk-load moment to tune against and no scheduled job anywhere
    # in this codebase to rebuild one. HNSW builds incrementally with no
    # size-tuning parameter and holds recall steady regardless of growth
    # pattern - the right tradeoff at this system's per-project row counts.
    # m/ef_construction are pgvector's own defaults, spelled out explicitly
    # so this is the one visible, greppable tuning point later.
    op.create_index(
        "ix_cards_embedding_hnsw",
        "cards",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_evidence_chunks_embedding_hnsw",
        "evidence_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.drop_index("ix_evidence_chunks_embedding_hnsw", table_name="evidence_chunks")
    op.drop_index("ix_cards_embedding_hnsw", table_name="cards")
    op.drop_column("evidence_chunks", "embedding")
    op.drop_column("cards", "embedding")
    json_type = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")
    op.add_column("cards", sa.Column("embedding", json_type, nullable=True))
    op.add_column("evidence_chunks", sa.Column("embedding", json_type, nullable=True))
