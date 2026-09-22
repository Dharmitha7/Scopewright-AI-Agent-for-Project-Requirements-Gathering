"""Groq client pool with API-key fallback on rate limits (D28).

Uses the official Groq SDK — no LiteLLM. When one key hits TPM/RPM
limits, the next configured key is tried before surfacing the error.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from groq import Groq

    from app.core.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T")


def resolved_groq_api_keys(settings: Settings) -> list[str]:
    """Primary ``GROQ_API_KEY`` plus optional comma-separated fallbacks.

    Each env value may itself be comma-separated. Order is preserved;
    duplicates are dropped.
    """
    keys: list[str] = []
    for source in (settings.groq_api_key, settings.groq_api_key_fallbacks):
        for part in source.split(","):
            token = part.strip()
            if token and token not in keys:
                keys.append(token)
    return keys


def groq_configured(settings: Settings) -> bool:
    return bool(resolved_groq_api_keys(settings))


class GroqClientPool:
    """Sticky Groq client selection with rotate-on-429."""

    def __init__(self, api_keys: list[str], *, max_retries_per_key: int = 2) -> None:
        if not api_keys:
            raise ValueError("GroqClientPool requires at least one API key")
        from groq import Groq

        self._clients: list[Groq] = [
            Groq(api_key=key, max_retries=max_retries_per_key) for key in api_keys
        ]
        self._key_index = 0

    @property
    def key_count(self) -> int:
        return len(self._clients)

    def execute(self, operation: Callable[[Groq], T]) -> T:
        """Run ``operation(client)``; try the next key on ``RateLimitError``."""
        import groq

        last_exc: Exception | None = None
        start = self._key_index
        for offset in range(len(self._clients)):
            idx = (start + offset) % len(self._clients)
            client = self._clients[idx]
            try:
                result = operation(client)
            except groq.RateLimitError as exc:
                last_exc = exc
                if len(self._clients) > 1:
                    log.warning(
                        "Groq rate limit on API key %d/%d — trying next key",
                        idx + 1,
                        len(self._clients),
                    )
                continue
            self._key_index = idx
            return result
        assert last_exc is not None
        raise last_exc


def get_groq_pool(settings: Settings) -> GroqClientPool:
    keys = resolved_groq_api_keys(settings)
    if not keys:
        raise ValueError("No Groq API keys configured")
    return GroqClientPool(keys)


def groq_pool_from_settings(settings: Settings) -> GroqClientPool | None:
    keys = resolved_groq_api_keys(settings)
    if not keys:
        return None
    return GroqClientPool(keys)
