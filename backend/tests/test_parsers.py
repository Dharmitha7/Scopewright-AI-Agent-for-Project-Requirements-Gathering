"""Intake parsers (D59, D71): the two formats Docling can't handle (.txt,
.srt), format routing, and the character-based chunker. Every
Docling-covered format is routed/tested in test_docling_parser.py instead -
Docling's own parsing logic isn't this repo's to test."""

import pytest

from app.services.parsers import chunk_text, chunk_upload, is_audio, is_image, is_supported

SRT = b"""1
00:00:01,000 --> 00:00:04,000
The vendor API uses OAuth.

2
00:00:05,000 --> 00:00:08,000
Rate limit is 120 requests per minute.
"""


def test_srt_strips_cue_numbers():
    # .srt has no Docling backend (D71) - stays on the legacy regex-based
    # subtitle stripper, unchanged.
    chunks = chunk_upload("meeting.srt", SRT)
    text = "\n".join(chunks)
    assert "The vendor API uses OAuth." in text
    assert "Rate limit is 120 requests per minute." in text
    assert "00:00" not in text


def test_txt_is_plain_passthrough():
    # .txt has no Docling backend at all (D71, confirmed live) - stays on a
    # plain UTF-8 decode.
    chunks = chunk_upload("notes.txt", b"Scope: rescheduling only in v1.")
    assert chunks == ["Scope: rescheduling only in v1."]


def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="unsupported format"):
        chunk_upload("malware.exe", b"whatever")


def test_format_routing():
    assert is_image("whiteboard.png")
    assert is_audio("standup.mp4")
    assert is_supported("deck.pptx")
    assert is_supported("budget.xlsx")
    assert not is_supported("malware.exe")


def test_chunk_text_splits_long_paragraphs():
    text = "para one\n\n" + ("x" * 3000)
    chunks = chunk_text(text, max_chars=1200, overlap=0)
    assert len(chunks) >= 3
    assert all(len(c) <= 1200 for c in chunks)


def test_chunk_text_overlaps_consecutive_chunks():
    # Two paragraphs, each padded so neither alone fits with the other in one
    # 1200-char chunk, forcing a boundary between them.
    para_a = "Alpha fact. " * 60
    para_b = "Beta fact. " * 60
    chunks = chunk_text(para_a + "\n\n" + para_b, max_chars=1200, overlap=150)
    assert len(chunks) >= 2
    tail = chunks[0][-100:].strip()
    assert tail and tail in chunks[1]


def test_chunk_text_sentence_aware_fallback():
    # A single oversized paragraph made of real sentences should split on
    # sentence boundaries, not mid-word, before falling back to a raw window.
    sentence = "The system shall record every stakeholder decision. "
    text = sentence * 40
    chunks = chunk_text(text, max_chars=1200, overlap=0)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.strip()
        # No mid-word cut: every chunk starts at a sentence boundary (capital
        # letter after the previous chunk's period), never mid-token.
        assert chunk[0].isupper() or chunk[0].isdigit()
