"""Local embeddings via EmbeddingGemma-300M (D70). Replaces the hosted
gemini-embedding-001 adapter - no API key, runs in-process via
sentence-transformers.

Two asymmetric entry points, not one uniform `.embed()`: EmbeddingGemma is
prompt-conditioned for retrieval quality - queries and stored
documents/facts use different task prefixes (`prompt_name=`). Verified
live against the installed model before wiring these in:
`SentenceTransformer("google/embeddinggemma-300m").prompts` for the exact
prompt-name keys, and that `transformers>=4.57` is what actually resolved
(see pyproject.toml comment - below that version the model silently runs
causal instead of bidirectional attention, no error, no warning, just
degraded embeddings - HF sentence-transformers issue #3725)."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import Settings
from app.core.embedding_config import EMBED_MODEL_ID, EMBEDDING_DIMENSIONS

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL_ID)


def _length_guard(vector: list[float]) -> list[float]:
    # Same defensive shape as the old Gemini adapter's: cards.embedding/
    # evidence_chunks.embedding are a real pgvector Vector(N) column, not a
    # schema-less JSON array - a wrong-length vector would fail at insert
    # time instead of failing softly like everything else here.
    if len(vector) != EMBEDDING_DIMENSIONS:
        log.warning(
            "embeddinggemma returned a %d-dim vector, expected %d - dropping it",
            len(vector),
            EMBEDDING_DIMENSIONS,
        )
        return []
    return vector


class EmbeddingGemmaEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Embeddings are an enhancement, never load-bearing: on any failure
        # (model load, OOM, etc.), return empty vectors so callers fall back
        # to text similarity instead of failing the whole chat turn or job.
        try:
            vectors = _model().encode(texts, prompt_name="Retrieval-document").tolist()
        except Exception as exc:
            log.warning("embeddinggemma unavailable, falling back to text similarity: %s", exc)
            return [[] for _ in texts]
        return [_length_guard(v) for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            return []
        try:
            vector = _model().encode(text, prompt_name="Retrieval-query").tolist()
        except Exception as exc:
            log.warning("embeddinggemma unavailable, falling back to text similarity: %s", exc)
            return []
        return _length_guard(vector)


class NoopEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return []


def get_embeddings(settings: Settings):
    if not settings.embeddings_enabled:
        return NoopEmbeddings()
    return EmbeddingGemmaEmbeddings()
