# CrewLane chunking and embedding evaluations

These are offline quality evaluations. They import the current production parser, chunker, and
embedding adapter, but they do not change API behavior, write to PostgreSQL, call the generation
LLM, create cards, or run the agent.

## What is tested

1. `run_chunking_eval.py` checks whether every gold fact survives inside at least one complete
   chunk. It also reports tiny chunks and exact duplicates and prints every produced chunk for
   manual inspection.
2. `run_embedding_eval.py` embeds those exact chunks using `Retrieval-document`, embeds queries
   using `Retrieval-query`, ranks by cosine similarity, and reports Recall@1/3/5 and MRR.

This deliberately does **not** test PostgreSQL FTS, RRF, cards, agent routing, augmentation, or
answer generation. Those belong to the next current-RAG baseline evaluation.

## Prerequisites

From the repository root:

```powershell
cd backend
uv sync --group dev
```

Docling and the local EmbeddingGemma model are normal backend dependencies. The first run may
need to obtain model files from Hugging Face if they are not already cached. If the model is
gated in your environment, authenticate with an appropriately scoped `HF_TOKEN`.

## 1. Run chunking evaluation

```powershell
cd backend
uv run python -m evals.run_chunking_eval
```

To make any missing complete gold fact fail the command:

```powershell
uv run python -m evals.run_chunking_eval --strict
```

Review both generated files:

```text
evals/reports/chunking_report.md
evals/reports/chunking_report.json
```

The Markdown report is intended for human inspection. The JSON report can later be used in CI.

## 2. Review and extend the gold set

Edit:

```text
evals/datasets/chunking_cases.json
```

For each fact, `required_terms` means all terms must coexist in at least one produced chunk. Add
real sanitized CrewLane documents under `evals/fixtures/`, then add their facts to the dataset.
Do not commit customer-confidential documents.

## 3. Run embedding-only evaluation

Run chunking first. Then:

```powershell
uv run python -m evals.run_embedding_eval
```

Strict mode fails only for malformed, empty, NaN, infinite, or wrong-width vectors:

```powershell
uv run python -m evals.run_embedding_eval --strict
```

Review:

```text
evals/reports/embedding_report.md
evals/reports/embedding_report.json
```

The query dataset is:

```text
evals/datasets/embedding_queries.json
```

Each query references one or more `fact_id` values from the chunking dataset. Relevant chunk IDs
are derived automatically from fact containment. Therefore, a missing relevant chunk is reported
as a chunking failure instead of incorrectly blaming the embedding model.

## How to interpret results

Suggested starting targets, to be refined with real project fixtures:

| Metric | Starting target |
|---|---:|
| Complete gold-fact containment | >= 95% |
| Negations and identifiers preserved | 100% |
| Valid 768-dimensional vectors | 100% |
| Semantic Recall@1 | >= 75% |
| Semantic Recall@3 | >= 90% |
| Semantic Recall@5 | >= 95% |
| MRR | >= 0.80 |

The included fixtures are an expanded synthetic regression corpus, not sufficient evidence for
a final model or threshold decision. Replace or extend them with sanitized examples representative
of actual CrewLane projects before tuning production constants.

## Next evaluation, after approval

After chunking and embeddings are accepted, create a separate retrieval baseline that compares:

```text
vector only
PostgreSQL FTS only
current vector + FTS + RRF(k=60), topK=5
```

Do not tune production `topK`, the `0.35` similarity floor, or RRF parameters from this embedding-
only harness.

## 4. Run the current PostgreSQL retrieval baseline

Start PostgreSQL and apply migrations, then run the evaluator:

```powershell
docker compose up -d postgres
cd backend
uv run alembic upgrade head
$env:PGVECTOR_TEST_DATABASE_URL="postgresql+psycopg://crewlane:crewlane@localhost:5432/crewlane"
uv run python -m evals.run_retrieval_eval
```

Git Bash equivalent:

```bash
docker compose up -d postgres
cd backend
uv run alembic upgrade head
PGVECTOR_TEST_DATABASE_URL='postgresql+psycopg://crewlane:crewlane@localhost:5432/crewlane' \
  uv run python -m evals.run_retrieval_eval
```

The evaluator creates a temporary project, upload, evidence chunks, and cards, runs real
PostgreSQL pgvector and FTS queries, writes reports, and deletes the temporary rows. It compares
vector search with multiple similarity floors, the legacy FTS/RRF baselines, and the structured
production hybrid retriever (vector + lexical FTS + exact anchors + weighted RRF).

Review:

```text
evals/reports/retrieval_baseline_report.md
evals/reports/retrieval_baseline_report.json
```

## Current production RAG flow

For a user turn, the runtime now follows this order:

1. A constrained router decides whether project retrieval is needed and creates a standalone
   query when enough conversational context exists.
2. Retrieval returns structured hits with stable record/source IDs, source type, provenance,
   per-channel scores/ranks, fused score, and timing metadata.
3. A bounded augmentation layer labels retrieved text as untrusted data and assigns `[S1]`,
   `[S2]`, and so on. Instructions inside uploaded evidence must not be followed.
4. The generator answers with source markers or explicitly says the evidence does not establish
   the answer.
5. Citation validation rejects nonexistent markers. A grounding judge checks that qualifiers,
   authority, status, negation, and numeric values agree with cited evidence; unsupported replies
   are replaced with an abstention.
6. Machine decisions and executions are stored in `retrieval_traces`, separate from the human
   audit trail, and are available at `GET /projects/{project_id}/retrieval-traces`.

Retrieval settings are environment-configurable in `Settings`: top K, candidate pool, vector
floor, RRF K, channel weights, minimum FTS rank, context budget, and trace enablement. No fixture
names, vendors, requirement IDs, or accepted file types are encoded into retrieval routing.
