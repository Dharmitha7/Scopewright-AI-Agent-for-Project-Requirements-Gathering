"""Docling: the sole parser and chunker for every format it supports (D71).

No flag, no fallback - amends D68, which shipped this optional and
extraction-only. A missing `docling` install now fails at Python-import
time (this module imports it at module level, on purpose, unlike D68's
deliberately-lazy/soft imports), which happens at app boot since
`parsers.py` imports this module transitively from `ingestion.py`.

Chunking goes straight `DocumentConverter -> DoclingDocument ->
HybridChunker -> contextualize()`, never through Markdown export - Docling's
structural understanding (headings, tables, list boundaries) and
token-aware sizing would be thrown away by flattening to Markdown text
first and re-splitting with a character-based chunker.

The chunker's tokenizer is EmbeddingGemma's own tokenizer (D70's
EMBED_MODEL_ID) - chunk token counts are sized against the tokenizer that
will actually embed them, not an unrelated default.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from io import BytesIO

from docling.chunking import HybridChunker
from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from app.core.config import get_settings
from app.core.embedding_config import EMBED_MODEL_ID

log = logging.getLogger(__name__)

# Every format Docling natively supports that this app also accepts as an
# upload (SUPPORTED_EXTENSIONS in parsers.py) - confirmed live against
# Docling's docs. Notably absent: .txt (Docling has no plain-text backend
# at all) and .srt (Docling supports WebVTT, not SRT - a different format).
DOCLING_EXTENSIONS = frozenset(
    {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".csv", ".md", ".markdown", ".vtt"}
)


@lru_cache(maxsize=1)
def _converter() -> DocumentConverter:
    return DocumentConverter()


@lru_cache(maxsize=1)
def _chunker() -> HybridChunker:
    # max_tokens is Settings.docling_max_chunk_tokens (D77), not a literal
    # here - environment-configurable for the same reason the rag_* settings
    # are: not tied to a particular document type or fixture.
    tokenizer = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained(EMBED_MODEL_ID),
        max_tokens=get_settings().docling_max_chunk_tokens,
    )
    return HybridChunker(tokenizer=tokenizer)


def chunk(filename: str, body: bytes) -> list[str]:
    stream = DocumentStream(name=filename, stream=BytesIO(body))
    dl_doc = _converter().convert(stream).document
    chunker = _chunker()
    chunks = [
        text.strip()
        for c in chunker.chunk(dl_doc=dl_doc)
        if (text := chunker.contextualize(chunk=c)).strip()
    ]
    if not chunks:
        raise ValueError("docling produced no chunks")
    log.info("docling produced %d chunk(s) from %s", len(chunks), filename)
    return chunks
