"""Single source of truth for the embedding model and vector width.

Local model (D70), not a hosted API: `google/embeddinggemma-300m`, run via
`sentence-transformers`. Its native output is 768-dim - no Matryoshka
truncation needed, and it happens to exactly match the pgvector
`Vector(768)` columns migration 0009 already committed to, so switching
models here needed no new migration.

Changing EMBED_MODEL_ID to a model with a different native width WOULD need
a new Alembic migration (the column width is fixed in Postgres `vector(N)`
DDL) and re-embedding every existing card/evidence_chunk at the new width -
neither constant is live-tunable via Settings.
"""

EMBED_MODEL_ID = "google/embeddinggemma-300m"
EMBEDDING_DIMENSIONS = 768
