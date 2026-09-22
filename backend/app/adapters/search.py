"""SerpAPI web search (D24, D31)."""

from __future__ import annotations

import httpx

from app.core.config import Settings


class SerpApiSearch:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, *, num: int = 5) -> list[dict]:
        response = httpx.get(
            "https://serpapi.com/search.json",
            # google_light: organic results only (no Knowledge Graph/AI
            # Overview/ads/local pack/shopping) - the only field this adapter
            # reads is organic_results, so the dropped blocks were always
            # wasted cost. Half the credits, ~40% faster than plain "google".
            params={"q": query, "api_key": self._api_key, "num": num, "engine": "google_light"},
            timeout=30.0,
        )
        response.raise_for_status()
        organic = response.json().get("organic_results") or []
        return [
            {
                "title": item.get("title") or "",
                "link": item.get("link") or "",
                "snippet": item.get("snippet") or "",
            }
            for item in organic[:num]
            if item.get("snippet")
        ]


class NoopSearch:
    def search(self, query: str, *, num: int = 5) -> list[dict]:
        return [
            {
                "title": "Scripted search result",
                "link": "https://example.com",
                "snippet": f"No SERPAPI_KEY — scripted feasibility for: {query[:120]}",
            }
        ]


def get_search(settings: Settings):
    if settings.serpapi_key:
        return SerpApiSearch(settings.serpapi_key)
    return NoopSearch()
