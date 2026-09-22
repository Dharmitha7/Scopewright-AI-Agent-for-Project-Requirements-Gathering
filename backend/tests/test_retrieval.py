"""Retrieval over cards and evidence chunks (D56, pgvector rework, D70).

On sqlite, _supports_pgvector() is always False, so these exercise the
preserved Python fallback path directly with hand-set embedding vectors -
no live model load, no dependency on real Postgres. The SQL-side pgvector
path (migration 0009) needs real Postgres, covered separately in
test_retrieval_pgvector.py.
"""

from app.models.account import Account
from app.models.card import Card
from app.models.evidence_chunk import EvidenceChunk
from app.models.project import Project
from app.models.upload import Upload
from app.services import belief as belief_service
from app.services import cards as cards_service
from app.services.retrieval import retrieval_context


def _project_with_account(db_session, email: str) -> Project:
    account = Account(email=email, display_name="Retrieval")
    db_session.add(account)
    db_session.commit()
    project = Project(
        name="Retrieval test",
        brief="Test retrieval",
        phase="planning",
        created_by_account_id=account.id,
    )
    db_session.add(project)
    db_session.commit()
    return project, account


class _FixedQueryEmbedder:
    """Stands in for get_embeddings() at the retrieval_context() call site,
    which only ever calls .embed_query() (D70's query/document split)."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_query(self, text: str) -> list[float]:
        return self._vector


class _FixedDocumentEmbedder:
    """Stands in for get_embeddings() at belief.embed_fact()'s call site,
    which only ever calls .embed_documents() (D70's query/document split)."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


def test_retrieval_ranks_by_cosine_similarity(db_session, monkeypatch):
    project, _account = _project_with_account(db_session, "retrieval-cos@example.com")
    close = Card(
        project_id=project.id,
        kind="requirement",
        coverage_area="scope",
        body="The system shall sync the calendar nightly.",
        status="confirmed",
        embedding=[1.0, 0.0, 0.0],
    )
    far = Card(
        project_id=project.id,
        kind="requirement",
        coverage_area="scope",
        body="The system shall log every export.",
        status="confirmed",
        embedding=[0.0, 1.0, 0.0],
    )
    db_session.add_all([close, far])
    db_session.commit()

    monkeypatch.setattr(
        "app.services.retrieval.get_embeddings",
        lambda settings: _FixedQueryEmbedder([1.0, 0.0, 0.0]),
    )

    context = retrieval_context(db_session, project.id, "sync the calendar")
    assert "sync the calendar nightly" in context
    assert "log every export" not in context  # cosine 0.0, below the 0.35 floor


def test_retrieval_falls_back_to_text_similarity_without_embeddings(db_session):
    project, _account = _project_with_account(db_session, "retrieval-text@example.com")
    close = Card(
        project_id=project.id,
        kind="requirement",
        coverage_area="scope",
        body="Managers approve vacation requests within one business day.",
        status="confirmed",
    )
    unrelated = Card(
        project_id=project.id,
        kind="requirement",
        coverage_area="data",
        body="Export formats are markdown, docx, and pdf.",
        status="confirmed",
    )
    db_session.add_all([close, unrelated])
    db_session.commit()

    # EMBEDDINGS_ENABLED=false in the test env (conftest.py) -> NoopEmbeddings
    # -> empty query vector -> _top_matches falls straight through to
    # _text_similarity.
    context = retrieval_context(db_session, project.id, "Managers approve vacation requests")
    assert "Managers approve vacation requests" in context


def test_retrieval_includes_evidence_chunks(db_session, monkeypatch):
    project, account = _project_with_account(db_session, "retrieval-chunk@example.com")
    upload = Upload(
        project_id=project.id,
        filename="notes.txt",
        content_type="text/plain",
        storage_key="projects/x/uploads/x/notes.txt",
        submitted_by_account_id=account.id,
        status="done",
    )
    db_session.add(upload)
    db_session.commit()

    chunk = EvidenceChunk(
        project_id=project.id,
        upload_id=upload.id,
        chunk_index=0,
        body="The vendor API rate limit is 120 requests per minute.",
        embedding=[1.0, 0.0, 0.0],
    )
    db_session.add(chunk)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.retrieval.get_embeddings",
        lambda settings: _FixedQueryEmbedder([1.0, 0.0, 0.0]),
    )

    context = retrieval_context(db_session, project.id, "vendor API rate limit")
    assert "rate limit is 120 requests per minute" in context
    assert "[S1] evidence:notes.txt#0" in context


def test_update_card_reembeds(db_session, monkeypatch):
    project, _account = _project_with_account(db_session, "reembed@example.com")
    card = Card(
        project_id=project.id,
        kind="requirement",
        coverage_area="scope",
        body="Original wording",
        status="confirmed",
    )
    db_session.add(card)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.belief.get_embeddings",
        lambda settings: _FixedDocumentEmbedder([0.4, 0.5, 0.6]),
    )

    updated = cards_service.update_card(db_session, project, card.id, "Revised wording")
    assert updated.embedding == [0.4, 0.5, 0.6]


def test_conflict_card_gets_embedding(db_session, monkeypatch):
    project, _account = _project_with_account(db_session, "conflict-embed@example.com")
    other = Card(
        project_id=project.id,
        kind="requirement",
        coverage_area="scope",
        body="Existing conflicting fact",
        status="confirmed",
    )
    db_session.add(other)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.belief.get_embeddings",
        lambda settings: _FixedDocumentEmbedder([0.1, 0.2, 0.3]),
    )

    card, meta = belief_service.add_conflicting_fact(
        db_session,
        project,
        area="scope",
        fact="New contradicting fact",
        source_ref="msg:1",
        other=other,
    )
    assert card.embedding == [0.1, 0.2, 0.3]
