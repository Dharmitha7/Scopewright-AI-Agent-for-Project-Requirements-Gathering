# CrewLane demo runbook (2026-08-19, branch demo/2026-08-19)

Local-only demo: docker compose, no deployment.

## Start

```bash
docker compose up -d        # needs .env with GROQ_API_KEY, SERPAPI_KEY, HF_TOKEN
# open http://localhost:3000, sign in with any name + email (no password)
```

Cold-start verified: `docker compose down && docker compose up -d` keeps all data.

## Demo state in the database

- **Bookclub Demo** — complete lifecycle. Charter with auto-feasibility (GO,
  cited sources), full 11-section SRS (FR/NFR numbering, Given/When/Then
  stories, traceability, gaps), Audit tab populated, md/docx/pdf exports work.
- **Critic Probe** — parked AT the Planning gate with 6 AI-reviewer findings
  visible on the acceptance panel. Shows the HITL moment: accept anyway or
  send an area back.

## Suggested flow (15 min)

1. **Front door** (2 min): new project — type a name + brief, attach a doc or
   audio file, paste a link. Point out "CrewLane reads all of it before asking
   a single question."
2. **Ingest-first opening** (2 min): the reading state, then the sourced
   read-back with the honest "What has NOT been stated" list.
3. **Interview** (4 min): answer one question with a chip, one vaguely — the
   coverage judge asks a targeted follow-up. Ask an aside ("what did the notes
   say about X?") — it retrieves and cites the upload.
4. **The gate on Critic Probe** (3 min): reviewer findings, Read full draft
   modal, revise-or-accept. Accepting records name + timestamp.
5. **Documents + Audit on Bookclub Demo** (4 min): SRS tabs (Document vs
   card-exact Audit view), exports, traceability section, Audit trail tab.

## Known risks and escapes

- **Groq free-tier quotas**: 200k tokens/day and 8k/min per model. The client
  retries short TPM waits automatically. If a hard 429 hits mid-demo, switch
  `GROQ_MODEL` in `.env` to `openai/gpt-oss-20b` (separate quota) and
  `docker compose up -d backend`.
- Feasibility research needs SERPAPI_KEY; if it fails, chat says so and the
  gate still opens (advisory by design).
- **RAG / evidence asides** need embeddings to load at startup (D70): local
  EmbeddingGemma-300M, gated on Hugging Face - set `HF_TOKEN` in `.env` after
  accepting the license at huggingface.co/google/embeddinggemma-300m. Without
  it, Postgres still keyword-searches uploads (D66); recreate backend after
  adding the token.
- **Docling parses every PDF/DOCX/PPTX/XLSX/HTML/CSV/MD/VTT upload (D71)** -
  no flag, no fallback. A bad upload of one of these formats fails that
  upload (status shows "failed" in the Evidence tab) rather than silently
  degrading to a weaker legacy parser.
- Wikipedia links 403 the fetcher (their WAF); use other sites for the
  paste-a-link moment.
- If a turn errors mid-stream, the message is not lost: the next send replays
  it (durable LangGraph resume).

## What is deliberately out

Jira push, auth/roles, deployment, phases 3-7, diarization.
