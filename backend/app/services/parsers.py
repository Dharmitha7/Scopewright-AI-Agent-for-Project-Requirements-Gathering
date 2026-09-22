"""Parse/chunk supported upload formats (D13, D39, D59, D71).

Docling is the sole parser+chunker for every format it supports (D71) - no
flag, no fallback (see docling_parser.py). The two formats Docling can't
handle at all - plain .txt (no backend) and .srt (WebVTT-only, not SRT) -
keep minimal dedicated handling here, same as audio (transcribed) and
images (described by a vision model), both handled in ingestion.py before
this module is ever reached.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services import docling_parser

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".vtt", ".srt", ".html", ".htm"}
DOC_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".mpeg", ".mpga"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | DOC_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS


def extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def is_supported(filename: str) -> bool:
    return extension(filename) in SUPPORTED_EXTENSIONS


def is_audio(filename: str) -> bool:
    return extension(filename) in AUDIO_EXTENSIONS


def is_image(filename: str) -> bool:
    return extension(filename) in IMAGE_EXTENSIONS


_CUE_TIMING = re.compile(r"^\s*(\d+\s*$|\d{1,2}:\d{2}.*-->.*)")


def _subtitle_text(body: bytes) -> str:
    """Spoken lines from an .srt transcript, timestamps and cue ids stripped.

    'name: line' speaker prefixes (Teams/Zoom exports) survive - they carry
    the dual-provenance signal (D13). .vtt moved to Docling (D71); this stays
    for .srt only, which Docling has no backend for."""
    lines: list[str] = []
    for raw in body.decode("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        if _CUE_TIMING.match(line):
            continue
        line = re.sub(r"<[^>]+>", "", line)  # strip cue markup like <v Speaker>
        if line:
            lines.append(line)
    return "\n".join(lines)


def chunk_upload(filename: str, body: bytes) -> list[str]:
    """Parse+chunk an uploaded document. Docling handles every format it
    covers (D71) - no gate, no fallback; a Docling failure raises straight
    through into the job-worker retry path (app/jobs/__init__.py)."""
    ext = extension(filename)
    if ext in docling_parser.DOCLING_EXTENSIONS:
        return docling_parser.chunk(filename, body)
    if ext == ".txt":
        return chunk_text(body.decode("utf-8", errors="replace").strip())
    if ext == ".srt":
        return chunk_text(_subtitle_text(body).strip())
    raise ValueError(f"unsupported format: {ext or '(no extension)'}")


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _pack(units: list[str], max_chars: int, joiner: str) -> list[str]:
    """Greedy-pack units (paragraphs or sentences) under max_chars - the same
    algorithm chunk_text() uses for paragraphs, reused for the sentence tier."""
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}{joiner}{unit}" if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = unit
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_oversized_paragraph(para: str, max_chars: int) -> list[str]:
    """Sentence-aware split first; the raw fixed-window cut is now the last
    resort - only when a single 'sentence' (no ./!/? found, e.g. a run-on
    transcript blob) is itself still over max_chars."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(para) if s.strip()]
    if len(sentences) <= 1:
        return [para[i : i + max_chars].strip() for i in range(0, len(para), max_chars)]
    pieces: list[str] = []
    for chunk in _pack(sentences, max_chars, " "):
        if len(chunk) > max_chars:
            pieces.extend(chunk[i : i + max_chars].strip() for i in range(0, len(chunk), max_chars))
        else:
            pieces.append(chunk)
    return pieces


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Character-based chunker for the two formats Docling can't parse
    (.txt, .srt) plus audio transcripts and image descriptions, which are
    plain generated text with no document structure for Docling to use
    anyway."""
    if not text.strip():
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    raw: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                raw.append(current.strip())
                current = ""
            raw.extend(_split_oversized_paragraph(para, max_chars))
            continue
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
        else:
            raw.append(current.strip())
            current = para
    if current.strip():
        raw.append(current.strip())

    if overlap <= 0 or len(raw) <= 1:
        return raw

    # Carry the tail of each chunk into the next one, so a fact or idea split
    # across a chunk boundary isn't invisible to whichever chunk it lands in
    # (retrieval/extraction see each chunk independently - no overlap meant
    # zero redundancy at boundaries).
    out = [raw[0]]
    for i in range(1, len(raw)):
        prefix = raw[i - 1][-overlap:]
        if " " in prefix:  # avoid starting the next chunk mid-word
            prefix = prefix.split(" ", 1)[1]
        out.append(f"{prefix} {raw[i]}".strip())
    return out
