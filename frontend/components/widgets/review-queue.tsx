"use client";

import type { ConflictItem } from "@/lib/api";

type Props = {
  conflicts: ConflictItem[];
  busy: boolean;
  onResolve: (conflictId: string, winnerCardId: string) => Promise<void>;
};

export function ReviewQueue({ conflicts, busy, onResolve }: Props) {
  if (conflicts.length === 0) return null;

  return (
    <div className="well-panel min-w-0 border-amber-600/30 bg-amber-50/70 p-4">
      <h2 className="text-sm font-semibold text-ink">Review queue</h2>
      <p className="mt-1 text-xs text-muted">
        Conflicting facts need a human pick — nothing is silently overwritten (D13).
      </p>
      <ul className="mt-3 space-y-3">
        {conflicts.map((c) => (
          <li key={c.id} className="min-w-0 rounded-xl border border-line bg-well p-3 text-sm">
            <p className="break-words font-medium text-ink">A: {c.card_a.body}</p>
            <p className="mt-2 break-words font-medium text-ink">B: {c.card_b.body}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="focus-ring rounded-lg border border-line bg-glass px-2.5 py-1 text-xs text-ink disabled:opacity-50"
                disabled={busy}
                onClick={() => void onResolve(c.id, c.card_a.id)}
              >
                Keep A
              </button>
              <button
                type="button"
                className="focus-ring rounded-lg border border-line bg-glass px-2.5 py-1 text-xs text-ink disabled:opacity-50"
                disabled={busy}
                onClick={() => void onResolve(c.id, c.card_b.id)}
              >
                Keep B
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
