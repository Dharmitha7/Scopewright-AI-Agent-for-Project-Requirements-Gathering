"use client";

import { useState } from "react";
import type { PhaseRedirectSuggestionWidget } from "@/lib/widgets";

export function PhaseRedirectSuggestion({
  widget,
  resolved,
  onGoToPlanning,
  onKeepHere,
}: {
  widget: PhaseRedirectSuggestionWidget;
  /** True once a later turn has moved past this suggestion. */
  resolved: boolean;
  onGoToPlanning: (planningArea: string | null) => void;
  onKeepHere: (excerpt: string) => void;
}) {
  const [busy, setBusy] = useState<"planning" | "here" | null>(null);

  if (resolved) {
    return <p className="mt-1 text-xs text-muted italic">Resolved — see the chat above.</p>;
  }

  return (
    <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5">
      <p className="text-xs text-amber-900">
        &ldquo;{widget.excerpt}&rdquo; sounds like a Planning-level change, not a Requirements
        detail.
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={busy !== null}
          className="rounded-lg border border-amber-300 bg-white px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-50"
          onClick={() => {
            setBusy("planning");
            onGoToPlanning(widget.planning_area);
          }}
        >
          {busy === "planning" ? "Opening…" : "Go to Planning"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          className="rounded-lg border border-line bg-white px-2.5 py-1 text-xs font-medium text-muted hover:bg-well disabled:opacity-50"
          onClick={() => {
            setBusy("here");
            onKeepHere(widget.excerpt);
          }}
        >
          {busy === "here" ? "Recording…" : "No, keep it here"}
        </button>
      </div>
    </div>
  );
}
