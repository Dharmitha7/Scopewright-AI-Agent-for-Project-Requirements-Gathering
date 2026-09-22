from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from evals.common import EVAL_ROOT, chunk_cases, resolve_dataset, write_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate CrewLane chunk containment.")
    parser.add_argument("--dataset", default="datasets/chunking_cases.json")
    parser.add_argument("--output-dir", default=str(EVAL_ROOT / "reports"))
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any gold fact is split.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = resolve_dataset(args.dataset)
    chunks, _fact_chunks, facts = chunk_cases(dataset_path)
    source_counts = Counter(chunk.source_id for chunk in chunks)
    failed = [fact for fact in facts if not fact["matching_chunks"]]
    tiny = [chunk for chunk in chunks if len(chunk.text.split()) < 20]
    duplicates = len(chunks) - len({" ".join(chunk.text.casefold().split()) for chunk in chunks})

    payload = {
        "dataset": str(dataset_path),
        "summary": {
            "sources": len(source_counts),
            "chunks": len(chunks),
            "gold_facts": len(facts),
            "contained_facts": len(facts) - len(failed),
            "fact_containment_rate": (len(facts) - len(failed)) / len(facts) if facts else 0,
            "tiny_chunks_under_20_words": len(tiny),
            "exact_duplicate_chunks": duplicates,
        },
        "source_chunk_counts": dict(source_counts),
        "facts": facts,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "phase": chunk.phase,
                "index": chunk.index,
                "characters": len(chunk.text),
                "approx_words": len(chunk.text.split()),
                "text": chunk.text,
            }
            for chunk in chunks
        ],
    }

    lines = [
        "# CrewLane chunking evaluation",
        "",
        f"- Sources: {len(source_counts)}",
        f"- Produced chunks: {len(chunks)}",
        f"- Gold facts contained in one chunk: {len(facts) - len(failed)}/{len(facts)}",
        f"- Tiny chunks (<20 words): {len(tiny)}",
        f"- Exact duplicate chunks: {duplicates}",
        "",
        "## Gold fact results",
        "",
        "| Result | Fact | Category | Matching chunks |",
        "|---|---|---|---|",
    ]
    for fact in facts:
        result = "PASS" if fact["matching_chunks"] else "FAIL"
        matches = ", ".join(fact["matching_chunks"]) or "none"
        lines.append(f"| {result} | {fact['fact_id']} | {fact['category']} | {matches} |")
    lines.extend(["", "## Produced chunks", ""])
    for chunk in chunks:
        lines.extend(
            [
                f"### {chunk.chunk_id}",
                "",
                f"Source: `{chunk.source_path}`  ",
                f"Characters: {len(chunk.text)} | Approx. words: {len(chunk.text.split())}",
                "",
                "```text",
                chunk.text,
                "```",
                "",
            ]
        )
    write_reports("chunking_report", payload, "\n".join(lines), Path(args.output_dir))
    print("\n".join(lines[:8]))
    print(f"Reports: {Path(args.output_dir).resolve()}")
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
