"""Load versioned agent skill packs (prompt/policy text) from disk.

Skills improve interview questions without changing graph control flow or
inventing facts (D72). Document composers use inline prompts. Missing ids are
skipped so callers can fall back safely.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_CONTENT = Path(__file__).resolve().parent / "content"


@lru_cache(maxsize=64)
def load_skill(skill_id: str) -> str:
    """Return skill markdown body, or "" if unknown / empty id."""
    key = (skill_id or "").strip().strip("/")
    if not key or ".." in key or key.startswith(("\\", "/")):
        return ""
    path = (_CONTENT / f"{key}.md").resolve()
    try:
        path.relative_to(_CONTENT.resolve())
    except ValueError:
        return ""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def skill_text(*skill_ids: str) -> str:
    """Join skill bodies in order; omit missing ids."""
    parts = [load_skill(sid) for sid in skill_ids]
    return "\n\n".join(p for p in parts if p)


def interview_skill_ids(phase_key: str) -> tuple[str, ...]:
    """Skills always applied to interview LLM system prompts for a phase."""
    return ("core_ba", f"interview/{phase_key}")
