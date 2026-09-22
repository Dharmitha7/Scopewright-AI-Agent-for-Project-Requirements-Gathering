"""Local cross-encoder reranking (retrieval-quality prototype, D-tbd).

A cross-encoder scores (query, candidate) pairs jointly instead of comparing
independently-computed embeddings - usually a real top-k quality bump over
bi-encoder cosine similarity, at the cost of one forward pass per candidate
rather than per corpus item. Small (~80MB), well-known MS MARCO checkpoint -
no new paid API, first run downloads from Hugging Face the same way
EmbeddingGemma already does (see adapters/embeddings.py).

Domain-agnostic on purpose, same reasoning as embeddings.py: this module
does not know about RetrievalHit/Card/EvidenceChunk. Callers map their own
(id, text) pairs in and (id, score) pairs back out.
"""

from __future__ import annotations

import logging
from functools import lru_cache

log = logging.getLogger(__name__)

CROSS_ENCODER_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(CROSS_ENCODER_MODEL_ID)


def rerank(
    query: str, candidates: list[tuple[str, str]], *, top_k: int
) -> list[tuple[str, float]]:
    """Re-score (id, text) candidates against ``query``; returns (id, score)
    sorted best-first, truncated to ``top_k``. Fails soft to the original
    order with score 0.0 on any model error - reranking is an enhancement,
    never load-bearing, same convention as EmbeddingGemmaEmbeddings."""
    if not candidates:
        return []
    try:
        scores = _model().predict([(query, text) for _id, text in candidates])
    except Exception as exc:
        log.warning("cross-encoder unavailable, keeping original order: %s", exc)
        return [(item_id, 0.0) for item_id, _text in candidates[:top_k]]
    ranked = sorted(
        zip((item_id for item_id, _text in candidates), scores, strict=True),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return [(item_id, float(score)) for item_id, score in ranked[:top_k]]
