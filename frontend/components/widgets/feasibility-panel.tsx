"use client";

import { useState } from "react";

type Source = { title: string; link: string; snippet: string };

type Props = {
  phase: string;
  busy: boolean;
  onRun: (query: string) => Promise<void>;
  lastReport?: { query: string; summary: string; sources: Source[] } | null;
};

export function FeasibilityPanel({ phase, busy, onRun, lastReport }: Props) {
  const [query, setQuery] = useState("");

  if (phase !== "planning") return null;

  return (
    <div className="well-panel min-w-0 p-4">
      <h2 className="text-sm font-semibold text-ink">Feasibility research (optional)</h2>
      <p className="mt-1 text-xs text-muted">
        Live web search with citations — recommendations only, never gating (D24).
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <input
          className="focus-ring min-w-[12rem] flex-1 rounded-lg border border-line bg-well px-2.5 py-1.5 text-sm"
          placeholder="e.g. competitors for …"
          value={query}
          disabled={busy}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button
          type="button"
          className="focus-ring rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-50"
          disabled={busy || query.trim().length < 3}
          onClick={() => void onRun(query.trim())}
        >
          {busy ? "Searching…" : "Research"}
        </button>
      </div>
      {lastReport && (
        <div className="mt-4 space-y-2 text-sm">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
            Query: {lastReport.query}
          </p>
          <p className="break-words whitespace-pre-wrap text-ink">{lastReport.summary}</p>
          <ul className="space-y-1 text-xs text-muted">
            {lastReport.sources.map((s) => (
              <li key={s.link} className="break-words">
                <a href={s.link} className="text-accent underline" target="_blank" rel="noreferrer">
                  {s.title}
                </a>
                {" — "}
                {s.snippet}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
