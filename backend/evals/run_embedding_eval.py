from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

from evals.common import EVAL_ROOT, chunk_cases, cosine, load_json, resolve_dataset, write_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate EmbeddingGemma over CrewLane chunks.")
    parser.add_argument("--chunk-dataset", default="datasets/chunking_cases.json")
    parser.add_argument("--query-dataset", default="datasets/embedding_queries.json")
    parser.add_argument("--output-dir", default=str(EVAL_ROOT / "reports"))
    parser.add_argument("--strict", action="store_true", help="Exit 1 if vectors are invalid.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chunk_path = resolve_dataset(args.chunk_dataset)
    query_path = resolve_dataset(args.query_dataset)
    chunks, fact_chunks, facts = chunk_cases(chunk_path)
    queries = load_json(query_path)["queries"]

    missing_facts = [fact["fact_id"] for fact in facts if not fact["matching_chunks"]]
    if missing_facts:
        print("WARNING: these gold facts have no complete chunk: " + ", ".join(missing_facts))

    from app.adapters.embeddings import EmbeddingGemmaEmbeddings
    from app.core.embedding_config import EMBED_MODEL_ID, EMBEDDING_DIMENSIONS

    embedder = EmbeddingGemmaEmbeddings()
    document_vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    invalid_documents = [
        chunks[index].chunk_id
        for index, vector in enumerate(document_vectors)
        if len(vector) != EMBEDDING_DIMENSIONS or not all(math.isfinite(v) for v in vector)
    ]

    rows = []
    category_rows: dict[str, list[dict]] = defaultdict(list)
    for query in queries:
        relevant = {
            chunk_id
            for fact_id in query["relevant_fact_ids"]
            for chunk_id in fact_chunks.get(fact_id, [])
        }
        query_vector = embedder.embed_query(query["query"])
        query_valid = len(query_vector) == EMBEDDING_DIMENSIONS and all(
            math.isfinite(value) for value in query_vector
        )
        ranking = []
        if query_valid and not invalid_documents:
            ranking = sorted(
                [
                    {"chunk_id": chunk.chunk_id, "score": cosine(query_vector, vector)}
                    for chunk, vector in zip(chunks, document_vectors, strict=True)
                ],
                key=lambda item: item["score"],
                reverse=True,
            )
        first_rank = next(
            (index for index, item in enumerate(ranking, start=1) if item["chunk_id"] in relevant),
            None,
        )
        row = {
            **query,
            "query_vector_valid": query_valid,
            "relevant_chunk_ids": sorted(relevant),
            "first_relevant_rank": first_rank,
            "recall_at_1": bool(first_rank and first_rank <= 1),
            "recall_at_3": bool(first_rank and first_rank <= 3),
            "recall_at_5": bool(first_rank and first_rank <= 5),
            "reciprocal_rank": 1 / first_rank if first_rank else 0,
            "top_5": ranking[:5],
        }
        rows.append(row)
        category_rows[query["category"]].append(row)

    def average(key: str, selected: list[dict]) -> float:
        return sum(float(row[key]) for row in selected) / len(selected) if selected else 0

    summary = {
        "model": EMBED_MODEL_ID,
        "dimensions": EMBEDDING_DIMENSIONS,
        "chunks": len(chunks),
        "queries": len(rows),
        "invalid_document_vectors": invalid_documents,
        "invalid_query_vectors": [row["query_id"] for row in rows if not row["query_vector_valid"]],
        "queries_without_relevant_chunk": [
            row["query_id"] for row in rows if not row["relevant_chunk_ids"]
        ],
        "recall_at_1": average("recall_at_1", rows),
        "recall_at_3": average("recall_at_3", rows),
        "recall_at_5": average("recall_at_5", rows),
        "mrr": average("reciprocal_rank", rows),
    }
    by_category = {
        category: {
            "queries": len(selected),
            "recall_at_1": average("recall_at_1", selected),
            "recall_at_3": average("recall_at_3", selected),
            "recall_at_5": average("recall_at_5", selected),
            "mrr": average("reciprocal_rank", selected),
        }
        for category, selected in sorted(category_rows.items())
    }
    payload = {
        "chunk_dataset": str(chunk_path),
        "query_dataset": str(query_path),
        "summary": summary,
        "by_category": by_category,
        "queries": rows,
    }

    lines = [
        "# CrewLane embedding evaluation",
        "",
        f"- Model: `{EMBED_MODEL_ID}`",
        f"- Dimensions: {EMBEDDING_DIMENSIONS}",
        f"- Chunks: {len(chunks)}",
        f"- Queries: {len(rows)}",
        f"- Recall@1: {summary['recall_at_1']:.3f}",
        f"- Recall@3: {summary['recall_at_3']:.3f}",
        f"- Recall@5: {summary['recall_at_5']:.3f}",
        f"- MRR: {summary['mrr']:.3f}",
        "",
        "## Query results",
        "",
        "| Query | Category | First relevant rank | R@1 | R@3 | R@5 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['query_id']} | {row['category']} | {row['first_relevant_rank'] or '-'} | "
            f"{int(row['recall_at_1'])} | {int(row['recall_at_3'])} | {int(row['recall_at_5'])} |"
        )
    lines.extend(["", "## Top-five details", ""])
    for row in rows:
        lines.extend([f"### {row['query_id']}: {row['query']}", ""])
        relevant_text = ", ".join(row["relevant_chunk_ids"]) or "none - chunking failure"
        lines.append("Relevant: " + relevant_text)
        lines.append("")
        for index, hit in enumerate(row["top_5"], start=1):
            marker = "RELEVANT" if hit["chunk_id"] in row["relevant_chunk_ids"] else ""
            lines.append(f"{index}. `{hit['chunk_id']}` score={hit['score']:.4f} {marker}")
        lines.append("")
    write_reports("embedding_report", payload, "\n".join(lines), Path(args.output_dir))
    print("\n".join(lines[:11]))
    print(f"Reports: {Path(args.output_dir).resolve()}")
    invalid = bool(invalid_documents or summary["invalid_query_vectors"])
    return 1 if args.strict and invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
