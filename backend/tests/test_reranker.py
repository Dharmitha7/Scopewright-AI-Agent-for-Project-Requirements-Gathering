from app.adapters import reranker


def test_rerank_sorts_by_score_and_truncates_to_top_k(monkeypatch) -> None:
    monkeypatch.setattr(
        reranker,
        "_model",
        lambda: type("FakeModel", (), {"predict": lambda self, pairs: [0.1, 0.9, 0.5]})(),
    )
    ranked = reranker.rerank("query", [("a", "low"), ("b", "high"), ("c", "mid")], top_k=2)
    assert ranked == [("b", 0.9), ("c", 0.5)]


def test_rerank_fails_soft_to_original_order_on_model_error(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(reranker, "_model", _boom)
    ranked = reranker.rerank("query", [("a", "x"), ("b", "y")], top_k=5)
    assert ranked == [("a", 0.0), ("b", 0.0)]


def test_rerank_empty_candidates_returns_empty() -> None:
    assert reranker.rerank("query", [], top_k=5) == []
