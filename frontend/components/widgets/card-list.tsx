"use client";

import { useState } from "react";
import type { Card } from "@/lib/api";

const SOURCE = "source";
const RETIRED = "retired";

type Props = {
  cards: Card[];
  busy: boolean;
  onEdit: (cardId: string, body: string) => Promise<void>;
  onRetire: (cardId: string) => Promise<void>;
};

export function CardList({ cards, busy, onEdit, onRetire }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const visible = cards.filter((c) => c.kind !== SOURCE && c.status !== RETIRED);

  const startEdit = (card: Card) => {
    setEditingId(card.id);
    setDraft(card.body);
  };

  const saveEdit = async () => {
    if (!editingId || !draft.trim()) return;
    await onEdit(editingId, draft.trim());
    setEditingId(null);
  };

  return (
    <div className="well-panel min-w-0 p-4">
      <h2 className="text-sm font-semibold text-ink">Knowledge cards</h2>
      <p className="mt-1 text-xs text-muted">
        Facts the AI recorded, newest first. Edit what is wrong; strike what does not belong.
      </p>
      {visible.length === 0 ? (
        <p className="mt-2 text-xs text-muted">No facts recorded yet.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {visible.map((card) => (
            <li key={card.id} className="group min-w-0 border-b border-line pb-2 last:border-0 last:pb-0">
              <p className="break-words text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
                {card.kind.replaceAll("_", " ")}
                {card.coverage_area ? ` · ${card.coverage_area.replaceAll("_", " ")}` : ""}
                {` · ${card.status}`}
                {card.sources.length > 0 ? ` · from ${card.sources.join(", ")}` : ""}
              </p>
              <p className="mt-0.5 font-mono text-[10px] text-muted/80">
                {new Date(card.created_at).toLocaleString()}
              </p>
              {editingId === card.id ? (
                <div className="mt-1 flex flex-col gap-2">
                  <textarea
                    className="focus-ring w-full resize-y rounded-lg border border-line bg-well px-2.5 py-1.5 text-sm"
                    rows={2}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="focus-ring rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-accent-ink disabled:opacity-50"
                      disabled={busy || !draft.trim()}
                      onClick={() => void saveEdit()}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="focus-ring rounded-lg border border-line px-2.5 py-1 text-xs text-ink"
                      onClick={() => setEditingId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-1 flex min-w-0 items-start justify-between gap-2">
                  <p className="min-w-0 flex-1 break-words text-sm text-ink">{card.body}</p>
                  <span className="flex shrink-0 gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      className="text-xs text-muted underline-offset-2 hover:underline disabled:opacity-50"
                      disabled={busy}
                      onClick={() => startEdit(card)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="text-xs text-muted underline-offset-2 hover:underline disabled:opacity-50"
                      disabled={busy}
                      onClick={() => void onRetire(card.id)}
                    >
                      Strike
                    </button>
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
