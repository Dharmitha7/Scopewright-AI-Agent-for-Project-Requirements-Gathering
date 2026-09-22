"""Draft changelog helpers (D83)."""

from app.core.config import get_settings
from app.services.draft_changelog import (
    CHANGELOG_END,
    CHANGELOG_START,
    draft_change_bullets,
    prepend_changelog,
    strip_changelog,
)


def test_prepend_and_strip_changelog() -> None:
    body = "# Title\n\nHello."
    with_log = prepend_changelog(body, ["First change", "Second change", "Third change"])
    assert CHANGELOG_START in with_log
    assert CHANGELOG_END in with_log
    assert "- First change" in with_log
    assert "# Title" in with_log
    assert strip_changelog(with_log) == body


def test_strip_is_noop_without_block() -> None:
    text = "# Clean\n\nNo block."
    assert strip_changelog(text) == text


def test_draft_change_bullets_initial_and_scripted() -> None:
    settings = get_settings()
    assert draft_change_bullets(settings, pack_title="Summary", previous="", current="# A") == [
        "Initial draft of this deliverable."
    ]
    bullets = draft_change_bullets(
        settings,
        pack_title="Summary",
        previous="# Old",
        current="# New content",
    )
    assert 3 <= len(bullets) <= 5
