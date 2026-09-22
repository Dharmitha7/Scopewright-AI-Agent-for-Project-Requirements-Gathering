from __future__ import annotations

import argparse
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from sqlalchemy import column, create_engine, delete, func, select
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import sessionmaker

from evals.common import EVAL_ROOT, chunk_cases, load_json, resolve_dataset, write_reports

RRF_K = 60
TOP_K = 5
POOL = 20
FLOORS = (None, 0.25, 0.30, 0.35, 0.40)
CARD_SEARCH_VECTOR = column("search_vector", type_=TSVECTOR)
CHUNK_SEARCH_VECTOR = column("search_vector", type_=TSVECTOR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate current PostgreSQL hybrid retrieval.")
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "PGVECTOR_TEST_DATABASE_URL",
            "postgresql+psycopg://crewlane:crewlane@localhost:5432/crewlane",
        ),
    )
    parser.add_argument("--chunk-dataset", default="datasets/chunking_cases.json")
    parser.add_argument("--card-dataset", default="datasets/retrieval_cards.json")
    parser.add_argument("--cases", default="datasets/retrieval_cases.json")
    parser.add_argument("--output-dir", default=str(EVAL_ROOT / "reports"))
    return parser.parse_args()


def rrf(*rankings: list[tuple[str, float]], limit: int = TOP_K) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, (item_id, _score) in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, 1))


def metrics(ranking: list[str], relevance: dict[str, int]) -> dict:
    direct = {item_id for item_id, grade in relevance.items() if grade == 3}
    useful = {item_id for item_id, grade in relevance.items() if grade >= 2}
    first_direct = next(
        (rank for rank, item_id in enumerate(ranking, 1) if item_id in direct), None
    )
    grades = [int(relevance.get(item_id, 0)) for item_id in ranking[:TOP_K]]
    ideal = sorted((int(value) for value in relevance.values()), reverse=True)[:TOP_K]
    ideal_dcg = dcg(ideal)
    no_answer = not relevance
    return {
        "answerable": not no_answer,
        "direct_recall_at_1": bool(first_direct and first_direct <= 1),
        "direct_recall_at_3": bool(first_direct and first_direct <= 3),
        "direct_recall_at_5": bool(first_direct and first_direct <= 5),
        "useful_recall_at_5": any(item_id in useful for item_id in ranking[:TOP_K]),
        "mrr": 1 / first_direct if first_direct else 0,
        "ndcg_at_5": dcg(grades) / ideal_dcg if ideal_dcg else (1.0 if not ranking else 0.0),
        "precision_at_5": sum(item_id in useful for item_id in ranking[:TOP_K]) / TOP_K,
        "no_answer_correct": (not ranking) if no_answer else None,
        "first_direct_rank": first_direct,
    }


def main() -> int:
    args = parse_args()
    # Production retrieval reads the same URL through Settings; keep the
    # standalone evaluator's direct engine and application settings aligned.
    os.environ.setdefault("DATABASE_URL", args.database_url)
    from app.adapters.embeddings import EmbeddingGemmaEmbeddings
    from app.adapters.reranker import rerank
    from app.models.account import Account
    from app.models.card import Card
    from app.models.evidence_chunk import EvidenceChunk
    from app.models.project import Project
    from app.models.upload import Upload
    from app.services.retrieval import retrieve

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    run_tag = uuid4().hex[:10]
    account = Account(email=f"rag-eval-{run_tag}@example.invalid", display_name="RAG Evaluation")
    session.add(account)
    session.flush()
    project = Project(
        name=f"RAG evaluation {run_tag}",
        brief="Controlled retrieval evaluation",
        phase="requirements",
        created_by_account_id=account.id,
    )
    session.add(project)
    session.flush()
    upload = Upload(
        project_id=project.id,
        filename="evaluation-corpus",
        content_type="text/plain",
        storage_key=f"eval/{run_tag}",
        submitted_by_account_id=account.id,
        status="done",
    )
    session.add(upload)
    session.flush()

    chunks, _fact_chunks, _facts = chunk_cases(resolve_dataset(args.chunk_dataset))
    card_rows = load_json(resolve_dataset(args.card_dataset))["cards"]
    cases = load_json(resolve_dataset(args.cases))["cases"]
    eval_text = {chunk.chunk_id: chunk.text for chunk in chunks}
    eval_text.update({row["item_id"]: row["body"] for row in card_rows})
    embedder = EmbeddingGemmaEmbeddings()
    all_texts = [chunk.text for chunk in chunks] + [row["body"] for row in card_rows]
    vectors = embedder.embed_documents(all_texts)
    if any(len(vector) != 768 for vector in vectors):
        raise RuntimeError("one or more corpus embeddings are missing or not 768-dimensional")

    db_to_eval: dict[str, str] = {}
    for index, chunk in enumerate(chunks):
        row = EvidenceChunk(
            project_id=project.id,
            upload_id=upload.id,
            chunk_index=index,
            body=chunk.text,
            embedding=vectors[index],
        )
        session.add(row)
        session.flush()
        db_to_eval[str(row.id)] = chunk.chunk_id
    offset = len(chunks)
    for index, item in enumerate(card_rows):
        row = Card(
            project_id=project.id,
            kind="requirement",
            coverage_area=item["coverage_area"],
            body=item["body"],
            status="confirmed",
            embedding=vectors[offset + index],
        )
        session.add(row)
        session.flush()
        db_to_eval[str(row.id)] = item["item_id"]
    session.commit()

    def vector(query_vector: list[float], floor: float | None) -> list[tuple[str, float]]:
        output: list[tuple[str, float]] = []
        for model in (Card, EvidenceChunk):
            distance = model.embedding.cosine_distance(query_vector)
            stmt = select(model.id, distance.label("distance")).where(
                model.project_id == project.id, model.embedding.is_not(None)
            )
            if floor is not None:
                stmt = stmt.where(distance < 1 - floor)
            rows = session.execute(stmt.order_by(distance).limit(POOL)).all()
            output.extend((db_to_eval[str(item_id)], 1 - float(dist)) for item_id, dist in rows)
        return sorted(output, key=lambda item: item[1], reverse=True)[:POOL]

    def fts(query: str) -> list[tuple[str, float]]:
        output: list[tuple[str, float]] = []
        tsquery = func.plainto_tsquery("simple", query)
        for model, search_col in ((Card, CARD_SEARCH_VECTOR), (EvidenceChunk, CHUNK_SEARCH_VECTOR)):
            rank = func.ts_rank(search_col, tsquery).label("rank")
            rows = session.execute(
                select(model.id, rank)
                .where(model.project_id == project.id, search_col.op("@@")(tsquery))
                .order_by(rank.desc())
                .limit(POOL)
            ).all()
            output.extend((db_to_eval[str(item_id)], float(score)) for item_id, score in rows)
        return sorted(output, key=lambda item: item[1], reverse=True)[:POOL]

    methods = [
        "vector_no_floor",
        "vector_0.25",
        "vector_0.30",
        "vector_0.35",
        "vector_0.40",
        "fts",
        "hybrid_0.25",
        "hybrid_0.30",
        "hybrid_0.35",
        "hybrid_0.40",
        "production_hybrid",
        # D-tbd: is the trigram-indexed exact-substring channel earning its
        # keep? Same production _fuse() call, just missing "exact" - a real
        # ablation, not a reimplementation. See DECISIONS.md D77.
        "production_hybrid_no_exact",
        # Local cross-encoder prototype: rerank the union of the wide
        # vector + FTS pools (already computed below for the vector_*/hybrid_*
        # rows) instead of the fused top TOP_K, so it can promote a candidate
        # the RRF fusion alone did not surface.
        "production_hybrid_reranked",
    ]
    query_rows = []
    timings: dict[str, list[float]] = defaultdict(list)
    for case in cases:
        query_vector = embedder.embed_query(case["query"])
        if len(query_vector) != 768:
            raise RuntimeError(f"query embedding failed for {case['query_id']}")
        start = time.perf_counter()
        no_floor = vector(query_vector, None)
        no_floor_ms = (time.perf_counter() - start) * 1000
        timings["vector_no_floor"].append(no_floor_ms)
        vector_runs = {}
        vector_ms = {}
        for floor in FLOORS[1:]:
            name = f"vector_{floor:.2f}"
            start = time.perf_counter()
            vector_runs[floor] = vector(query_vector, floor)
            vector_ms[floor] = (time.perf_counter() - start) * 1000
            timings[name].append(vector_ms[floor])
        start = time.perf_counter()
        keyword = fts(case["query"])
        keyword_ms = (time.perf_counter() - start) * 1000
        timings["fts"].append(keyword_ms)
        rankings = {"vector_no_floor": no_floor[:TOP_K], "fts": keyword[:TOP_K]}
        for floor, results in vector_runs.items():
            rankings[f"vector_{floor:.2f}"] = results[:TOP_K]
            name = f"hybrid_{floor:.2f}"
            start = time.perf_counter()
            rankings[name] = rrf(results, keyword)
            fusion_ms = (time.perf_counter() - start) * 1000
            timings[name].append(vector_ms[floor] + keyword_ms + fusion_ms)
        start = time.perf_counter()
        production = retrieve(session, project.id, case["query"])
        timings["production_hybrid"].append((time.perf_counter() - start) * 1000)
        rankings["production_hybrid"] = [
            (db_to_eval[hit.record_id], hit.fused_score)
            for hit in production.hits
            if hit.record_id in db_to_eval
        ]

        start = time.perf_counter()
        no_exact = retrieve(
            session, project.id, case["query"], exclude_channels=frozenset({"exact"})
        )
        timings["production_hybrid_no_exact"].append((time.perf_counter() - start) * 1000)
        rankings["production_hybrid_no_exact"] = [
            (db_to_eval[hit.record_id], hit.fused_score)
            for hit in no_exact.hits
            if hit.record_id in db_to_eval
        ]

        start = time.perf_counter()
        pool_ids = list(
            dict.fromkeys(
                [item_id for item_id, _ in no_floor] + [item_id for item_id, _ in keyword]
            )
        )
        candidates = [(item_id, eval_text.get(item_id, "")) for item_id in pool_ids]
        rankings["production_hybrid_reranked"] = rerank(case["query"], candidates, top_k=TOP_K)
        timings["production_hybrid_reranked"].append(
            no_floor_ms + keyword_ms + (time.perf_counter() - start) * 1000
        )
        query_rows.append(
            {
                "query_id": case["query_id"],
                "query": case["query"],
                "category": case["category"],
                "relevance": case["relevance"],
                "methods": {
                    name: {
                        "ranking": [
                            {"item_id": item_id, "score": score}
                            for item_id, score in rankings[name]
                        ],
                        "metrics": metrics(
                            [item_id for item_id, _ in rankings[name]], case["relevance"]
                        ),
                    }
                    for name in methods
                },
            }
        )

    def avg(method: str, key: str) -> float:
        values = []
        for row in query_rows:
            result = row["methods"][method]["metrics"]
            if result[key] is None:
                continue
            if key != "no_answer_correct" and not result["answerable"]:
                continue
            values.append(result[key])
        return sum(float(value) for value in values) / len(values) if values else 0

    summary = {}
    for method in methods:
        summary[method] = {
            key: avg(method, key)
            for key in (
                "direct_recall_at_1",
                "direct_recall_at_3",
                "direct_recall_at_5",
                "useful_recall_at_5",
                "mrr",
                "ndcg_at_5",
                "precision_at_5",
                "no_answer_correct",
            )
        }
        summary[method]["mean_latency_ms"] = (
            sum(timings[method]) / len(timings[method]) if timings[method] else 0
        )

    payload = {
        "configuration": {"rrf_k": RRF_K, "top_k": TOP_K, "pool": POOL, "database_url": "redacted"},
        "corpus": {"chunks": len(chunks), "cards": len(card_rows), "queries": len(cases)},
        "summary": summary,
        "queries": query_rows,
    }
    lines = [
        "# CrewLane PostgreSQL retrieval baseline",
        "",
        (
            f"Corpus: {len(chunks)} evidence chunks + {len(card_rows)} cards | "
            f"Queries: {len(cases)} | topK={TOP_K} | RRF k={RRF_K}"
        ),
        "",
        "## Method comparison",
        "",
        "| Method | R@1 | R@3 | R@5 | Useful R@5 | MRR | nDCG@5 | P@5 | No-answer | Mean ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in methods:
        s = summary[method]
        lines.append(
            "| {method} | {r1:.3f} | {r3:.3f} | {r5:.3f} | {ur5:.3f} | "
            "{mrr:.3f} | {ndcg:.3f} | {p5:.3f} | {no_answer:.3f} | {ms:.2f} |".format(
                method=method,
                r1=s["direct_recall_at_1"],
                r3=s["direct_recall_at_3"],
                r5=s["direct_recall_at_5"],
                ur5=s["useful_recall_at_5"],
                mrr=s["mrr"],
                ndcg=s["ndcg_at_5"],
                p5=s["precision_at_5"],
                no_answer=s["no_answer_correct"],
                ms=s["mean_latency_ms"],
            )
        )
    lines.extend(["", "## Per-query rankings", ""])
    for row in query_rows:
        lines.extend([f"### {row['query_id']}: {row['query']}", ""])
        for method in methods:
            ranked = (
                ", ".join(
                    f"{hit['item_id']} ({hit['score']:.4f})"
                    for hit in row["methods"][method]["ranking"]
                )
                or "no results"
            )
            lines.append(f"- **{method}:** {ranked}")
        lines.append("")
    write_reports("retrieval_baseline_report", payload, "\n".join(lines), Path(args.output_dir))
    print("\n".join(lines[:20]))
    print(f"Reports: {Path(args.output_dir).resolve()}")

    session.rollback()
    session.execute(delete(EvidenceChunk).where(EvidenceChunk.project_id == project.id))
    session.execute(delete(Card).where(Card.project_id == project.id))
    session.execute(delete(Upload).where(Upload.project_id == project.id))
    session.execute(delete(Project).where(Project.id == project.id))
    session.execute(delete(Account).where(Account.id == account.id))
    session.commit()
    session.close()
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
