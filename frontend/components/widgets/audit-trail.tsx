"use client";

import { useMemo, useState } from "react";
import type { AuditEvent } from "@/lib/api";

type Props = {
  events: AuditEvent[];
  detailFor: (event: AuditEvent) => string;
};

function startOfDay(isoDate: string): number {
  const d = new Date(isoDate);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function endOfDay(isoDate: string): number {
  const d = new Date(isoDate);
  d.setHours(23, 59, 59, 999);
  return d.getTime();
}

function kindLabel(kind: string): string {
  return kind.replaceAll("_", " ");
}

export function AuditTrail({ events, detailFor }: Props) {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  const kinds = useMemo(() => {
    const unique = [...new Set(events.map((e) => e.kind))];
    return unique.sort((a, b) => kindLabel(a).localeCompare(kindLabel(b)));
  }, [events]);

  const filtered = useMemo(() => {
    let rows = [...events];
    if (fromDate) {
      const from = startOfDay(fromDate);
      rows = rows.filter((e) => new Date(e.created_at).getTime() >= from);
    }
    if (toDate) {
      const to = endOfDay(toDate);
      rows = rows.filter((e) => new Date(e.created_at).getTime() <= to);
    }
    if (kindFilter) {
      rows = rows.filter((e) => e.kind === kindFilter);
    }
    return rows.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, [events, fromDate, toDate, kindFilter]);

  const hasFilters = Boolean(fromDate || toDate || kindFilter);

  return (
    <div>
      <h2 className="text-sm font-semibold text-ink">Audit trail</h2>
      <p className="mt-1 text-xs text-muted">Human decisions and interview answers, newest first.</p>

      <div className="mt-3 flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted">From</span>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="focus-ring rounded-lg border border-line bg-well px-2 py-1 text-xs text-ink"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted">To</span>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="focus-ring rounded-lg border border-line bg-well px-2 py-1 text-xs text-ink"
            />
          </label>
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted">Type</span>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            className="focus-ring rounded-lg border border-line bg-well px-2 py-1 text-xs text-ink"
          >
            <option value="">All types</option>
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {kindLabel(kind)}
              </option>
            ))}
          </select>
        </label>
        {hasFilters && (
          <button
            type="button"
            className="focus-ring self-start text-xs text-accent hover:underline"
            onClick={() => {
              setFromDate("");
              setToDate("");
              setKindFilter("");
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {events.length === 0 ? (
        <p className="mt-3 text-xs text-muted">No decisions recorded yet.</p>
      ) : filtered.length === 0 ? (
        <p className="mt-3 text-xs text-muted">No events match these filters.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {filtered.map((event) => {
            const detail = detailFor(event);
            return (
              <li key={event.id} className="border-b border-line pb-2 text-xs last:border-0">
                <span className="font-medium text-ink">{event.actor}</span>{" "}
                <span className="text-accent">{kindLabel(event.kind)}</span>
                <span className="block font-mono text-[10px] text-muted">
                  {new Date(event.created_at).toLocaleString()}
                </span>
                {detail && <span className="mt-0.5 block break-words text-muted">{detail}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
