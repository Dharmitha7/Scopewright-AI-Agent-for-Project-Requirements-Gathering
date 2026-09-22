from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVAL_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ProducedChunk:
    chunk_id: str
    source_id: str
    source_path: str
    phase: str
    index: int
    text: str


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_dataset(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else EVAL_ROOT / path


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def contains_terms(text: str, terms: list[str]) -> bool:
    haystack = normalize(text)
    return all(normalize(term) in haystack for term in terms)


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def chunk_cases(dataset_path: Path) -> tuple[list[ProducedChunk], dict[str, list[str]], list[dict]]:
    # Settings.database_url has no default (real app boot should fail loud
    # without one) - but this chunking-only path never touches Postgres, and
    # neither run_chunking_eval.py nor run_embedding_eval.py set DATABASE_URL
    # (see evals/README.md's documented commands), unlike run_retrieval_eval.py
    # which does. docling_parser.py reads Settings for docling_max_chunk_tokens
    # (D77), so the whole Settings object must construct even though nothing
    # here uses database_url - give it a harmless placeholder rather than
    # make every eval script remember to set one.
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    # Imported lazily so --help and dataset validation do not load Docling.
    from app.services.parsers import chunk_upload

    dataset = load_json(dataset_path)
    chunks: list[ProducedChunk] = []
    fact_chunks: dict[str, list[str]] = {}
    fact_rows: list[dict] = []
    for case in dataset["cases"]:
        source_path = EVAL_ROOT / case["path"]
        bodies = chunk_upload(source_path.name, source_path.read_bytes())
        source_chunks = []
        for index, body in enumerate(bodies):
            chunk = ProducedChunk(
                chunk_id=f"{case['source_id']}#chunk-{index}",
                source_id=case["source_id"],
                source_path=case["path"],
                phase=case["phase"],
                index=index,
                text=body,
            )
            chunks.append(chunk)
            source_chunks.append(chunk)
        for fact in case["facts"]:
            matching = [
                chunk.chunk_id
                for chunk in source_chunks
                if contains_terms(chunk.text, fact["required_terms"])
            ]
            fact_chunks[fact["fact_id"]] = matching
            fact_rows.append({**fact, "source_id": case["source_id"], "matching_chunks": matching})
    return chunks, fact_chunks, fact_rows


def write_reports(stem: str, payload: dict, markdown: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stem}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / f"{stem}.md").write_text(markdown, encoding="utf-8")
