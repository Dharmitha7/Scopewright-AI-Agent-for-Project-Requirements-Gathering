"""EmbeddingGemmaEmbeddings (D70): query/document prompt split, the
dimension guard, and the never-load-bearing failure contract.

cards.embedding/evidence_chunks.embedding are a real pgvector Vector(N)
column (migration 0009), not a schema-less JSON array - a wrong-length
vector would fail at insert time rather than fail softly like every other
case in this class. These tests fake the model (no real sentence-transformers
load, no network, no gated HF download needed in CI) to prove the prompt
split and the guard actually work.
"""

from app.adapters.embeddings import EmbeddingGemmaEmbeddings


class _FakeArray:
    """Mimics the .tolist() surface of the numpy array .encode() returns -
    real sentence-transformers output, not a plain Python list."""

    def __init__(self, data):
        self._data = data

    def tolist(self):
        return self._data


class _RecordingModel:
    """Fakes SentenceTransformer.encode(), recording (input, prompt_name)
    so tests can assert the query/document prompt split actually happens -
    the one piece of new behavior this adapter has that the old Gemini one
    didn't need."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls: list[tuple] = []

    def encode(self, texts_or_text, prompt_name=None):
        self.calls.append((texts_or_text, prompt_name))
        if isinstance(texts_or_text, str):
            return _FakeArray(list(self._vector))
        return _FakeArray([list(self._vector) for _ in texts_or_text])


def test_embed_query_uses_query_prompt(monkeypatch):
    model = _RecordingModel([0.1, 0.2, 0.3])
    monkeypatch.setattr("app.adapters.embeddings.EMBEDDING_DIMENSIONS", 3)
    monkeypatch.setattr("app.adapters.embeddings._model", lambda: model)

    result = EmbeddingGemmaEmbeddings().embed_query("find the calendar sync requirement")

    assert result == [0.1, 0.2, 0.3]
    assert model.calls == [("find the calendar sync requirement", "Retrieval-query")]


def test_embed_documents_uses_document_prompt(monkeypatch):
    model = _RecordingModel([0.1, 0.2, 0.3])
    monkeypatch.setattr("app.adapters.embeddings.EMBEDDING_DIMENSIONS", 3)
    monkeypatch.setattr("app.adapters.embeddings._model", lambda: model)

    result = EmbeddingGemmaEmbeddings().embed_documents(["a fact", "another fact"])

    assert result == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert model.calls == [(["a fact", "another fact"], "Retrieval-document")]


def test_embed_drops_wrong_dimension_vector(monkeypatch):
    # Pretend the model returned a 2-dim vector when 3 was expected.
    monkeypatch.setattr("app.adapters.embeddings.EMBEDDING_DIMENSIONS", 3)
    monkeypatch.setattr(
        "app.adapters.embeddings._model", lambda: _RecordingModel([0.1, 0.2])
    )

    embedder = EmbeddingGemmaEmbeddings()

    # Empty list/vector - the same "no embedding" signal every caller already
    # treats safely (e.g. `embedding or None`), never the malformed vector.
    assert embedder.embed_documents(["some fact"]) == [[]]
    assert embedder.embed_query("some query") == []


def test_embed_keeps_correctly_sized_vector(monkeypatch):
    monkeypatch.setattr("app.adapters.embeddings.EMBEDDING_DIMENSIONS", 3)
    monkeypatch.setattr(
        "app.adapters.embeddings._model", lambda: _RecordingModel([0.1, 0.2, 0.3])
    )

    embedder = EmbeddingGemmaEmbeddings()

    assert embedder.embed_documents(["some fact"]) == [[0.1, 0.2, 0.3]]
    assert embedder.embed_query("some query") == [0.1, 0.2, 0.3]


def test_embed_documents_falls_back_on_model_failure(monkeypatch):
    def _boom():
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.adapters.embeddings._model", _boom)

    result = EmbeddingGemmaEmbeddings().embed_documents(["a", "b"])
    assert result == [[], []]


def test_embed_query_falls_back_on_model_failure(monkeypatch):
    def _boom():
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.adapters.embeddings._model", _boom)

    assert EmbeddingGemmaEmbeddings().embed_query("some query") == []
