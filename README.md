# CrewLane

Ground-up rethink **v1 complete** (Planning → Requirements, end to end). Readable plan: [`docs/crewlane-rethink.html`](docs/crewlane-rethink.html). Binding decisions: [`DECISIONS.md`](DECISIONS.md). **Demo study:** [`docs/crewlane-demo-cheatsheet.html`](docs/crewlane-demo-cheatsheet.html) (short) · [`docs/crewlane-system-mastery.html`](docs/crewlane-system-mastery.html) (full). The 2026-07-31 demo is on [`demo/2026-07-31`](../../branch/demo/2026-07-31).

Runnable monorepo: FastAPI + Next.js, local Postgres + MinIO, session sign-in wall, a **Claude-like signed-in shell** (D82: collapsible project rail + fixed-width chat + context panel), a **real LangGraph interview** (Planning + Requirements, durable gates), **live AG-UI SSE chat streaming** (D58/D62), **intake from everywhere** (D59: documents txt/md/pdf/docx/xlsx/pptx/csv, transcripts vtt/srt, pasted links, whiteboard images via Groq vision, audio/video with ffmpeg chunking + Groq Whisper, and in-browser voice recording), belief layer + hybrid retrieval with conflict review (D56/D57/D63–D77), evidence-classified facts that advance coverage with confirmation questions (D59), human card edit/strike (D62), **selectable Requirements deliverable packs** in chat (D70/D71/D84), **post-complete free-form chat + Requirements redraft** (D83), **hybrid documents** (D60): deterministic audit view + LLM narrative, exportable as md/docx/pdf, and **personal OneDrive publish** under `/CrewLane/{ProjectName}/…` (D85).

## What this is

An AI system that runs a software project's lifecycle with a human decision at every gate. Agents draft; named humans accept. Documents (Charter, SRS) are views of a typed card model — not files anyone maintains.

v1 scope: Planning + Requirements only. Phase 1 is **single-user** (D43): one operator, no membership table. Jira, Teams, and phases 3–7 are deferred.

## Layout

```
backend/app/
  main.py            FastAPI app factory, include_router, lifespan
  dependencies.py    shared Depends (session, current account)
  core/config.py     THE only place env is read (Pydantic Settings)
  core/db.py         SQLAlchemy engine / session
  core/security.py   JWT in HttpOnly session cookie (D53)
  routers/           health, auth, projects (+ messages, stream, cards, gate, uploads)
  models/            accounts, projects, messages, jobs, uploads, evidence_chunks,
                     cards, strings, snapshots
  schemas/           Pydantic request/response
  services/          sole writer path (projects, chat, stream, cards, belief,
                     retrieval, ingestion, documents, onedrive, draft_changelog)
  adapters/          storage (S3/MinIO), embeddings (local EmbeddingGemma-300M, D73)
  jobs/              in-process worker when JOB_WORKER_ENABLED=true (D32);
                     handles ingest_upload + onedrive_sync (D85)
  agents/            LangGraph phase-runner: templates.py (phases as data, D18),
                     graph.py (6 nodes, 2 interrupts: answer wait + gate), runner.py
                     (threads, checkpointer, gate-time snapshot, redraft + post-complete),
                     knowledge.py (KnowledgePort seam - CardKnowledge, D51-D52),
                     card_kinds.py, deliverables.py (pack catalog, D70), inference.py
                     (Groq, or scripted stand-in without a key)
frontend/app/        Next.js App Router — signed-in shell for / and /projects/{id}
frontend/components/ shell (AppShell, project rail, context tabs) + trusted widgets
                     (D50/D71): question, conflict, feasibility, deliverable picker,
                     acceptance panel, evidence preview
frontend/lib/          api.ts, stream.ts (AG-UI SSE client), widgets.ts, deliverables.ts
```

FastAPI structure follows [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/). Settings follow [Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/).

## Run locally

1. Copy `.env.example` to `.env` if you do not already have one. Keep `DEV_AUTH=true` for the session wall. Do not commit `.env`.
2. From the repo root:

   ```bash
   docker compose up -d --build
   ```

3. UI: http://localhost:3000 — **Continue** with a display name and email. After sign-in you get the **Claude-like shell** (D82): left project list (`+` creates), centered chat (~48rem), right Artifacts / Coverage / Audit / Knowledge.
4. Open a project → the agent mirrors what it knows, then interviews across the phase areas (open-ended answers + **I don't know / N/A** — not multiple choice, D16). Chat uses **`POST /projects/{id}/messages/stream`** (AG-UI SSE: `RUN_STARTED` → `MESSAGE` × N → `RUN_FINISHED`, D58). With `GROQ_API_KEY` unset, a deterministic scripted stand-in answers; set the key and `GROQ_MODEL` in `.env` for real LLM behavior (default: `openai/gpt-oss-120b`; older Groq models may be retired).
5. When Planning coverage is complete, **Accept / Revise** appear **in chat** (D71). Accepting opens Requirements seeded from Planning (D27).
6. At the Requirements gate, **select deliverable packs** (separate documents only — D84) → **Generate** → review → **Accept**. After Accept (`phase=done`), keep chatting free-form, or use **Redraft requirements** to regenerate packs / bump `final/vN.0` (D83).
7. **Upload evidence** under Artifacts (or the composer attach control) — files land in MinIO, a background worker parses/transcribes, chunks, and extracts facts into cards (D55/D74). Preview opens the **original file** via `GET /projects/{id}/uploads/{id}/content` (D82). Set `GROQ_API_KEY` for real LLM extraction and Whisper transcription; set `HF_TOKEN` for local EmbeddingGemma (D73).
8. Optional **OneDrive** (D85): set Microsoft OAuth env vars (see below), restart backend, avatar menu → **Connect OneDrive**. Or set `ONEDRIVE_LOCAL_MIRROR_DIR` for a disk mirror of the same tree. API docs: http://localhost:8000/docs.

Rebuild after **code** changes (`--build`). After **.env** only, `docker compose up -d --force-recreate backend`.

Docker Compose starts **MinIO** on http://localhost:9001 (console) and enables the ingestion worker by default. MinIO credentials are set in `docker-compose.yml`; override via `.env` if needed.

If this machine already ran the old demo, the Docker volume `pgdata` may not have a `crewlane` database (it had `crewlane_v2`). Either create it (`CREATE DATABASE crewlane TEMPLATE template0;`) or wipe local DB data with `docker compose down -v` and start again. `-v` deletes that volume.

### Host processes (optional)

Postgres and MinIO still come from Compose. Then:

```bash
docker compose up -d postgres minio
cd backend && uv sync --group dev && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

Set `JOB_WORKER_ENABLED=true` in `.env` for the ingestion worker on the host API. Set `S3_ENDPOINT=http://localhost:9000` (and keys from `.env.example`) to use MinIO from the host.

## Auth (D42–D44, D53) + Microsoft OneDrive (D85)

No Stytch. Phase 1 uses a **JWT in an HttpOnly cookie** (not localStorage, not a public bearer):

1. **Continue** → `POST /auth/dev-session` with display name + email.
2. Backend upserts an `accounts` row (same email = same person) and sets `crewlane_session` to an HS256 JWT (`sub` = account id, 14-day `exp`).
3. Protected routes read `account_id` from that cookie (D53).
4. **Sign out** → `POST /auth/logout` clears the cookie.

There is no password. This is enough for a single-user internal demo and for the audit trail (display name + account id on accept actions later). External IdP (original D7) is deferred until the app is semi-public with real credentials.

**Personal OneDrive publish (D85):** optional. Source of truth stays Postgres snapshots; OneDrive is a markdown mirror under `/CrewLane/{ProjectName}/planning|requirements/{draft,final/vN.0}/`. Sync jobs use the **project creator’s** linked Microsoft account. Env (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` | Azure app registration (personal accounts) |
| `MICROSOFT_REDIRECT_URI` | Default `http://localhost:8000/auth/microsoft/callback` |
| `MICROSOFT_TENANT` | Default `consumers` (personal MSA) |
| `ONEDRIVE_LOCAL_MIRROR_DIR` | If set, writes the same tree to disk and skips Graph (tests/demo) |

Routes: `GET /auth/microsoft/start|callback|status`, `POST /auth/microsoft/disconnect`. Avatar menu → Connect / Disconnect. Leave `MICROSOFT_CLIENT_ID` empty to disable OAuth. Worker must be on (`JOB_WORKER_ENABLED=true` in Compose) for sync jobs to run.

## Tests

```bash
cd backend
uv run ruff check .
uv run pytest -q
# Deliverables / gate / redraft / OneDrive coverage bar (≥80% on touched modules)
uv run pytest -q \
  --cov=app.agents.deliverables --cov=app.services.documents \
  --cov=app.agents.graph --cov=app.agents.runner --cov=app.agents.inference \
  --cov=app.services.onedrive --cov=app.services.draft_changelog \
  --cov-report=term-missing --cov-fail-under=80 \
  tests/test_deliverables.py tests/test_documents.py tests/test_agents.py \
  tests/test_cards.py tests/test_e2e_v1.py \
  tests/test_draft_changelog.py tests/test_onedrive.py
```

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

Includes **E2E lifecycle tests** (`tests/test_e2e_v1.py`): full Planning → Requirements (pack select) → done → free-form chat → redraft → Accept (version bump), SSE stream, upload/ingest.

## OpenAPI → TypeScript (D37)

```bash
cd backend
uv run python scripts/export_openapi.py ../frontend/openapi.json
```

The frontend `lib/api.ts` is handwritten against those routes until CI generates the client.

## Docs (update with every PR)

Binding decisions live in [`DECISIONS.md`](DECISIONS.md). The readable plan is [`docs/crewlane-rethink.html`](docs/crewlane-rethink.html). **When you change behavior, env vars, or recorded decisions, update those files and this README in the same PR** — not as a follow-up.

## Knowledge model (D22, D51–D52)

`app/agents/knowledge.py`'s `CardKnowledge` is the `KnowledgePort` implementation the graph talks to — same three methods (`say`, `record_facts`, `planning_digest`) as the interim `MessageKnowledge` it replaced, so the graph itself never changed. `record_facts` writes candidate `cards` plus a `supported-by` string to a `source` card (one per chat message, reused across every fact it supports) via `app/services/cards.py`; `app/agents/card_kinds.py` maps every Planning/Requirements coverage-area key to one of D22's 15 card kinds, as data. The `fact_log` widget is still dual-written on every `say()` so the workspace UI (D50) keeps working unchanged. At gate accept, `runner.py`'s `on_accept()` promotes that phase's cards to `accepted` and freezes a `snapshots` row — `card_versions` is a JSONB array of `{card_id, version}` pointers (D51), not a document copy.

`GET /projects/{id}/snapshots` renders Charter/SRS markdown from snapshot pointers (D54) — no LLM in that path.

## Ingestion (D13, D55, D59)

Uploads: `POST /projects/{id}/uploads` (multipart file + optional `speaker_name` for dual provenance); `POST /projects/{id}/links` fetches a web page into the same pipeline; the workspace has an **in-browser voice recorder**. Raw bytes go to object storage; a `jobs` row drives the in-process worker (`ingest_upload`). Supported formats: **documents** (txt, md, pdf, docx, xlsx, pptx, csv, html), **transcripts** (vtt, srt - speaker prefixes kept), **images** (png, jpg, webp, gif - described by Groq vision), and **audio/video** (wav, mp3, m4a, mp4, webm, ogg, flac) via Groq Whisper; long or non-Groq formats are converted and chunked with ffmpeg. Limits: 25 MB per document, 200 MB for audio. The worker chunks text, extracts candidate facts and **classifies each into a phase coverage area** (D59), writes `evidence_chunks`, and records cards with `supported-by` → `upload:{id}` source refs. The interviewer then **confirms** areas that evidence already covers instead of re-asking. All facts pass through the **belief layer** (D56): duplicates corroborate to `confirmed`, contradictions get `conflicts-with` edges, and resolving a conflict retires the loser (D62).

**Relevance filtering (D86):** once a project has a real scope (a brief of some length, or recorded facts — the very first uploads to a brand-new project are exempt, since they often define that scope), each chunk is classified on-topic or not in the same extraction call — an off-topic chunk is never stored (no `evidence_chunks` row, no card), so junk can't leak into cards or retrieval even from an otherwise-relevant document. If *every* chunk in an upload is off-topic, the upload is marked `status=flagged` and a chat card offers **Keep anyway / Discard** (`POST /projects/{id}/uploads/{id}/keep|discard`) — never silently rejected.

## Belief and retrieval (D56, D63–D77)

`record_facts` (chat and ingestion) runs through `app/services/belief.py`: near-duplicate facts promote the existing card to **`confirmed`** and add another `supported-by` string; likely contradictions create a new candidate card plus a **`conflicts-with`** edge (LLM check when `GROQ_API_KEY` is set, text similarity fallback otherwise). `GET /projects/{id}/conflicts` lists open pairs; `POST .../conflicts/{id}/resolve` picks the winning card.

Embeddings: **local EmbeddingGemma-300M** via `sentence-transformers` when `EMBEDDINGS_ENABLED=true` (default; forced off in tests). Needs a Hugging Face token (`HF_TOKEN`) and license acceptance for `google/embeddinggemma-300m` (D73). On Postgres, retrieval is **hybrid** (pgvector HNSW + FTS + exact channel, D63–D77). Without embeddings, keyword FTS still runs on Postgres. Vectors are `Vector(768)` on `cards` / `evidence_chunks`. Interview turns can call a **bounded** `search_project_evidence` tool once (D81).

## AG-UI chat streaming (D58)

User turns post to **`POST /projects/{id}/messages/stream`**. The backend runs the LangGraph turn in a worker thread and emits AG-UI-shaped SSE frames **as messages commit** (D62): `RUN_STARTED`, one `MESSAGE` per committed row (full `MessageOut` JSON, including widgets), then `RUN_FINISHED` (`RUN_ERROR` on failure). The frontend client (`frontend/lib/stream.ts`) reads the body incrementally, so the read-back appears before the question. Gate actions and feasibility still use REST. CopilotKit was not added — the graph stays transport-agnostic (D48); the widget catalog was extended instead (D61: question batches, confirm cards, markdown rendering).

## Conflict review and feasibility (D57)

Conflicts emit a **`conflict_card`** in chat; the workspace **review queue** resolves them (keep A or B). Optional **feasibility research** during Planning: `POST /projects/{id}/feasibility` runs SerpAPI (`SERPAPI_KEY`) + Groq summary with cited `feasibility_report` widget. Never gating (D24).

## Documents, redraft, and OneDrive (D60 / D70–D71 / D83–D85)

At Planning gate accept the Charter snapshot is frozen (card pointers) **and** an LLM narrative is composed (`snapshots.narrative`). At Requirements gate the user **must** select deliverable packs (separate documents only — D84) before generate; Accept freezes `snapshots.narratives` (per-pack markdown) plus a display `narrative`. Artifacts lists **accepted** documents; **Document** / **Audit** expand with **md / docx / pdf** export (optional `?pack=`).

Stories use **What / Why / How** and Happy/Sad acceptance criteria (Given/When/Then; And optional). Gate Accept/Revise and the Requirements pack picker appear **in chat** (D71).

After Requirements Accept (`phase=done`), chat stays open for free-form Q&A; **Redraft requirements** regenerates packs and bumps a new final version (D83). Draft markdown can carry a short changelog; finals never do. Published markdown mirrors to the project creator’s personal OneDrive (or `ONEDRIVE_LOCAL_MIRROR_DIR`) under `/CrewLane/{ProjectName}/planning|requirements/{draft,final/vN.0}/` (D85) — Accept still succeeds if sync is queued for retry.

## Signed-in shell (D82)

`/` and `/projects/{id}` share `AppShell`: collapsible left project rail (avatar Sign out + optional OneDrive connect), fixed-width centered chat (~48rem; does not grow when side panels open), right context panel (Artifacts / Coverage / Audit / Knowledge). Create project from `+`. Evidence under Artifacts previews the original upload, not RAG chunks.

## Not built yet (post-v1)

Multi-user membership. Speaker diarization for multi-speaker audio (skipped for now, free-tier services exist). CopilotKit/A2UI React renderer (full D11 generative UI) — the extended trusted widget catalog (D61/D71) covers v1. Email-in and native Teams connectors (D13 deferrals). LangGraph checkpointer tables are created at **app startup** (D49), outside Alembic. Hybrid RAG v2 (reranker, ingest relevance gate) and out-of-process job workers remain follow-ons.
