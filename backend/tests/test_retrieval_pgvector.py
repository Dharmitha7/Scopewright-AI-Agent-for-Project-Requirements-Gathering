"""First-ever Postgres-only test in this repo - deliberately opt-in.

Every other test runs on sqlite (see conftest.py, which unconditionally
forces DATABASE_URL to sqlite:///:memory: at import time, before pytest
even collects, so gating on DATABASE_URL can't work - a separate env var is
the only way to opt in without touching that hermetic default). This proves
the one thing the sqlite fallback tests (test_retrieval.py, test_belief.py)
cannot: that the real pgvector Vector(768) column, HNSW index, and
.cosine_distance() comparator wiring (migration 0009) actually work against
real Postgres, not just plausible-looking Python.

Assumes migrations are already applied (`uv run alembic upgrade head`
against the target DB) - this file only reads/writes rows, it never touches
schema, so it's safe to run against a real dev database without disturbing
its migration state.

Run locally via `docker compose up -d postgres`, `uv run alembic upgrade head`,
then:
  PGVECTOR_TEST_DATABASE_URL=postgresql+psycopg://crewlane:crewlane@localhost:5432/crewlane \
    uv run pytest tests/test_retrieval_pgvector.py -v
Not part of the default `pytest` invocation.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("PGVECTOR_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not PG_URL, reason="set PGVECTOR_TEST_DATABASE_URL to run pgvector integration tests"
)


def _vec(dominant: int, dims: int = 768) -> list[float]:
    """A simple one-hot-ish 768-dim vector, distinguishable by cosine angle."""
    v = [0.01] * dims
    v[dominant] = 1.0
    return v


@pytest.fixture
def pg_session():
    engine = create_engine(PG_URL)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    created_account_ids: list = []
    try:
        yield session, created_account_ids
    finally:
        # Clean up only the rows this test created - never touches schema,
        # so the DB's migration state (verified separately) stays untouched.
        from sqlalchemy import delete

        from app.models.account import Account
        from app.models.card import Card
        from app.models.evidence_chunk import EvidenceChunk
        from app.models.project import Project
        from app.models.string import CardString
        from app.models.upload import Upload

        session.rollback()
        for account_id in created_account_ids:
            project_ids = [
                row[0]
                for row in session.execute(
                    Project.__table__.select().where(Project.created_by_account_id == account_id)
                ).all()
            ]
            for pid in project_ids:
                card_ids = [
                    row[0]
                    for row in session.execute(
                        Card.__table__.select().where(Card.project_id == pid)
                    ).all()
                ]
                session.execute(
                    delete(CardString).where(
                        CardString.from_card_id.in_(card_ids) | CardString.to_card_id.in_(card_ids)
                    )
                )
                session.execute(delete(EvidenceChunk).where(EvidenceChunk.project_id == pid))
                session.execute(delete(Upload).where(Upload.project_id == pid))
                session.execute(delete(Card).where(Card.project_id == pid))
                session.execute(delete(Project).where(Project.id == pid))
            session.execute(delete(Account).where(Account.id == account_id))
        session.commit()
        session.close()
        engine.dispose()


def _project_with_account(session, created_account_ids, email: str):
    from app.models.account import Account
    from app.models.project import Project

    account = Account(email=email, display_name="PGVector")
    session.add(account)
    session.commit()
    created_account_ids.append(account.id)
    project = Project(
        name="pgvector test", brief="pgvector integration", phase="planning",
        created_by_account_id=account.id,
    )
    session.add(project)
    session.commit()
    return project, account


def test_sql_retrieval_finds_nearest_card(pg_session):
    from app.models.card import Card
    from app.services.retrieval import retrieval_context

    session, created_account_ids = pg_session
    project, _account = _project_with_account(
        session, created_account_ids, "pgv-retrieval@example.com"
    )
    close = Card(
        project_id=project.id, kind="requirement", coverage_area="scope",
        body="The system shall sync the calendar nightly.",
        status="confirmed", embedding=_vec(0),
    )
    far = Card(
        project_id=project.id, kind="requirement", coverage_area="scope",
        body="The system shall log every export.",
        status="confirmed", embedding=_vec(1),
    )
    session.add_all([close, far])
    session.commit()

    import app.services.retrieval as retrieval_module

    class _FixedEmbedder:
        def embed_query(self, text):
            return _vec(0)

    orig = retrieval_module.get_embeddings
    retrieval_module.get_embeddings = lambda settings: _FixedEmbedder()
    try:
        context = retrieval_context(session, project.id, "sync the calendar")
    finally:
        retrieval_module.get_embeddings = orig

    assert "sync the calendar nightly" in context
    assert "log every export" not in context


def test_sql_duplicate_lookup_finds_nearest_above_threshold(pg_session):
    from app.services import belief as belief_service

    session, created_account_ids = pg_session
    project, _account = _project_with_account(session, created_account_ids, "pgv-dup@example.com")
    card, outcome, _meta = belief_service.assimilate_fact(
        session, project, area="scope", fact="Scope includes mobile apps",
        source_ref="msg:1", embedding=_vec(0),
    )
    assert outcome == "new"

    near = _vec(0)
    near[1] = 0.05  # perturb slightly, still well above the 0.92 similarity floor
    match_card, match_outcome, _meta2 = belief_service.assimilate_fact(
        session, project, area="scope", fact="Totally different wording",
        source_ref="msg:2", embedding=near,
    )
    assert match_outcome == "corroborated"
    assert match_card.id == card.id


def test_hybrid_search_finds_exact_term_vector_alone_would_miss(pg_session):
    """The concrete case D66 exists for: an exact product name whose
    embedding is deliberately pointed far from the query vector here (vector
    channel's 0.35 similarity floor would drop it) still surfaces through
    full-text search (migration 0010) - and RRF fusion in retrieval_context()
    lets it into the final result alongside a normal vector match, not one
    or the other."""
    import app.services.retrieval as retrieval_module
    from app.models.evidence_chunk import EvidenceChunk
    from app.models.upload import Upload

    session, created_account_ids = pg_session
    project, account = _project_with_account(session, created_account_ids, "pgv-hybrid@example.com")

    upload = Upload(
        project_id=project.id, filename="vendor-call.txt", content_type="text/plain",
        storage_key="x", submitted_by_account_id=account.id, status="done",
    )
    session.add(upload)
    session.commit()

    # Vector-findable: identical to the query embedding by design.
    vector_only = EvidenceChunk(
        project_id=project.id, upload_id=upload.id, chunk_index=0,
        body="The team discussed calendar sync cadence for next quarter.",
        embedding=_vec(0),
    )
    # Keyword-findable only: embedding points far enough away that cosine
    # similarity lands below the 0.35 floor, so only the exact "Mindbody"
    # token (via full-text search) can surface this one.
    keyword_only = EvidenceChunk(
        project_id=project.id, upload_id=upload.id, chunk_index=1,
        body="Mindbody was named as the incumbent scheduling vendor to replace.",
        embedding=_vec(700),
    )
    session.add_all([vector_only, keyword_only])
    session.commit()

    class _FixedEmbedder:
        def embed_query(self, text):
            return _vec(0)

    orig = retrieval_module.get_embeddings
    retrieval_module.get_embeddings = lambda settings: _FixedEmbedder()
    try:
        context = retrieval_module.retrieval_context(session, project.id, "Mindbody vendor")
    finally:
        retrieval_module.get_embeddings = orig

    assert "Mindbody was named" in context  # keyword channel only
    assert "calendar sync cadence" in context  # vector channel only


def test_keyword_only_search_works_without_an_embedding(pg_session):
    """EMBEDDINGS_ENABLED=false (this test's env, see conftest.py) ->
    NoopEmbeddings -> no query vector at all. Exact-token recall shouldn't
    need one: the keyword-only channel should still find an exact match on
    Postgres instead of dropping straight to the O(n) text-similarity scan."""
    from app.models.evidence_chunk import EvidenceChunk
    from app.models.upload import Upload
    from app.services.retrieval import retrieval_context

    session, created_account_ids = pg_session
    project, account = _project_with_account(session, created_account_ids, "pgv-kwonly@example.com")

    upload = Upload(
        project_id=project.id, filename="sow.txt", content_type="text/plain",
        storage_key="x", submitted_by_account_id=account.id, status="done",
    )
    session.add(upload)
    session.commit()
    chunk = EvidenceChunk(
        project_id=project.id, upload_id=upload.id, chunk_index=0,
        body="Contract reference SOW-2024-11 covers the pilot phase only.",
    )
    session.add(chunk)
    session.commit()

    context = retrieval_context(session, project.id, "SOW-2024-11")
    assert "SOW-2024-11" in context
