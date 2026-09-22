# CrewLane frontend

Next.js App Router: sign-in wall, project list, dual-surface project workspace (D10).

- **Chat (left):** persistent thread via **AG-UI SSE stream** (`lib/stream.ts`, D58), `question_card` + `fact_log` widgets, open-ended composer + N/A (D16 — not multiple choice)
- **Workspace (right):** coverage meter, gate panel, evidence upload, review queue, feasibility (Planning), card list, Charter/SRS (D54)
- **Widget types:** defined in `lib/widgets.ts`, rendered under `components/widgets/`

Run from the repo root [README](../README.md). **Every PR updates** `README.md`, `DECISIONS.md`, and `docs/crewlane-rethink.html` when behavior or decisions change.
