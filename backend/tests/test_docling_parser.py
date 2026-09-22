"""Docling routing (D71) - mocked; real docling not required in CI.

D68's flag/fallback tests are gone: there's no flag and no fallback left to
test. What's left to test is (a) chunk_upload() delegates every
Docling-covered extension straight to docling_parser.chunk() with no
re-splitting, and (b) a Docling failure raises straight through - no
legacy parser to catch it anymore.
"""

import pytest

from app.services.parsers import chunk_upload


def test_docling_covered_extension_delegates_to_chunker(monkeypatch):
    monkeypatch.setattr(
        "app.services.parsers.docling_parser.chunk",
        lambda _filename, _body: ["chunk one", "chunk two"],
    )

    assert chunk_upload("brief.pdf", b"anything") == ["chunk one", "chunk two"]


def test_docling_covered_extension_includes_xlsx_html_csv_md_vtt(monkeypatch):
    seen: list[str] = []

    def _fake_chunk(filename: str, _body: bytes) -> list[str]:
        seen.append(filename)
        return ["a chunk"]

    monkeypatch.setattr("app.services.parsers.docling_parser.chunk", _fake_chunk)

    for filename in (
        "brief.pdf", "stakeholders.docx", "deck.pptx", "budget.xlsx",
        "page.html", "risks.csv", "notes.md", "meeting.vtt",
    ):
        assert chunk_upload(filename, b"anything") == ["a chunk"]
    assert seen == [
        "brief.pdf", "stakeholders.docx", "deck.pptx", "budget.xlsx",
        "page.html", "risks.csv", "notes.md", "meeting.vtt",
    ]


def test_docling_failure_raises_no_fallback(monkeypatch):
    def _boom(_filename: str, _body: bytes) -> list[str]:
        raise RuntimeError("docling unavailable")

    monkeypatch.setattr("app.services.parsers.docling_parser.chunk", _boom)

    # No legacy parser left to catch this (D71) - it's the job worker's
    # existing retry/failure path (app/jobs/__init__.py) that handles it now.
    with pytest.raises(RuntimeError, match="docling unavailable"):
        chunk_upload("stakeholders.docx", b"anything")


def test_txt_and_srt_never_reach_docling(monkeypatch):
    def _fail_if_called(_filename: str, _body: bytes) -> list[str]:
        raise AssertionError("docling_parser.chunk should not be called for .txt/.srt")

    monkeypatch.setattr("app.services.parsers.docling_parser.chunk", _fail_if_called)

    assert chunk_upload("notes.txt", b"plain text") == ["plain text"]
    assert chunk_upload("meeting.srt", b"1\n00:00:01,000 --> 00:00:02,000\nHello.\n") == ["Hello."]
