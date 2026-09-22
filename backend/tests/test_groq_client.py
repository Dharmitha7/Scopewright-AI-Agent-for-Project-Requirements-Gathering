from types import SimpleNamespace
from unittest.mock import patch

import groq
import pytest

from app.adapters.groq_client import (
    GroqClientPool,
    groq_configured,
    resolved_groq_api_keys,
)
from app.core.config import Settings


def _groq_response() -> SimpleNamespace:
    return SimpleNamespace(request=SimpleNamespace(), status_code=429)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://x:x@localhost/x",
        "groq_api_key": "",
        "groq_api_key_fallbacks": "",
    }
    base.update(overrides)
    return Settings(**base)


def test_resolved_groq_api_keys_primary_and_fallbacks():
    settings = _settings(
        groq_api_key=" key-a , key-b ",
        groq_api_key_fallbacks="key-c, key-b",
    )
    assert resolved_groq_api_keys(settings) == ["key-a", "key-b", "key-c"]


def test_groq_configured_false_when_empty():
    assert groq_configured(_settings()) is False


def test_groq_configured_true_with_primary_only():
    assert groq_configured(_settings(groq_api_key="only")) is True


def test_groq_pool_requires_at_least_one_key():
    with pytest.raises(ValueError, match="at least one"):
        GroqClientPool([])


def test_groq_pool_falls_back_on_rate_limit():
    calls: list[str] = []

    def operation(client):
        calls.append(client.label)
        if client.label == "first":
            raise groq.RateLimitError(
                "rate limited", response=_groq_response(), body=None
            )
        return f"ok:{client.label}"

    pool = GroqClientPool.__new__(GroqClientPool)
    pool._clients = [
        SimpleNamespace(label="first"),
        SimpleNamespace(label="second"),
    ]
    pool._key_index = 0

    assert pool.execute(operation) == "ok:second"
    assert calls == ["first", "second"]
    assert pool._key_index == 1


def test_groq_pool_raises_when_all_keys_rate_limited():
    pool = GroqClientPool.__new__(GroqClientPool)
    pool._clients = [SimpleNamespace(label="a"), SimpleNamespace(label="b")]
    pool._key_index = 0

    def operation(_client):
        raise groq.RateLimitError("rate limited", response=_groq_response(), body=None)

    with pytest.raises(groq.RateLimitError):
        pool.execute(operation)


def test_groq_pool_does_not_fallback_on_other_errors():
    pool = GroqClientPool.__new__(GroqClientPool)
    pool._clients = [SimpleNamespace(label="a"), SimpleNamespace(label="b")]
    pool._key_index = 0

    def operation(_client):
        raise groq.AuthenticationError("bad key", response=_groq_response(), body=None)

    with pytest.raises(groq.AuthenticationError):
        pool.execute(operation)


@patch("groq.Groq")
def test_groq_pool_sticky_to_working_key(mock_groq_ctor):
    first = SimpleNamespace(label="first")
    second = SimpleNamespace(label="second")
    mock_groq_ctor.side_effect = [first, second]
    pool = GroqClientPool(["k1", "k2"])

    assert pool.execute(lambda client: client.label) == "first"
    assert pool.execute(lambda client: client.label) == "first"
