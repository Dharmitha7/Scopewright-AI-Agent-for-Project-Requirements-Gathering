"use client";

import { useState } from "react";
import { DocModal } from "@/components/doc-modal";
import { Markdown } from "@/components/markdown";
import { coverageStatusLabel, type AcceptancePanelWidget } from "@/lib/widgets";
import { packLabels } from "@/lib/deliverables";

type Props = {
  widget: AcceptancePanelWidget;
  busy: boolean;
  lastSnapshotId?: string | null;
  compact?: boolean;
  onAccept: () => void;
  onRevise: (area: string, content: string) => void;
  onRetryGenerate?: (packIds: string[]) => void;
};

export function AcceptancePanel({
  widget,
  busy,
  lastSnapshotId,
  compact = false,
  onAccept,
  onRevise,
  onRetryGenerate,
}: Props) {
  const [reviseArea, setReviseArea] = useState("");
  const [expanded, setExpanded] = useState(false);

  const areas = Object.entries(widget.coverage).map(([key, status]) => ({
    key,
    label: key.replaceAll("_", " "),
    status: status as "pending" | "answered" | "na" | "skipped",
  }));
  const revisable = areas.filter((a) => ["answered", "na", "skipped"].includes(a.status));
  const failedPacks = widget.failed_packs ?? [];
  const generationBlocked = failedPacks.length > 0;

  return (
    <div
      className={`min-w-0 rounded-xl border border-accent/20 bg-well shadow-sm ${compact ? "p-3" : "p-4 sm:p-5"}`}
    >
      <p className="text-[11px] font-medium tracking-[0.12em] uppercase text-muted">Gate</p>
      <h2 className="mt-2 text-base font-semibold text-ink">Accept {widget.document}</h2>
      <p className="mt-2 text-xs text-muted">
        Preview below; use Read full draft for the complete document before you accept.
        Accept records your name, timestamp, and card versions.
        {lastSnapshotId ? ` Last snapshot: ${lastSnapshotId.slice(0, 8)}.` : ""}
      </p>
      {widget.selected_packs && widget.selected_packs.length > 0 && (
        <p className="mt-2 text-xs text-muted">
          Packs: {packLabels(widget.selected_packs)} · separate
        </p>
      )}
      {generationBlocked && (
        <div className="mt-3 rounded-xl border border-rose-300 bg-rose-50 p-3">
          <p className="text-xs font-semibold text-rose-900">
            Generation failed for: {packLabels(failedPacks)}
          </p>
          <p className="mt-1 text-xs text-rose-800">
            Re-run Generate selected before Accept. A failed pack is not the same as
            missing facts.
          </p>
          {onRetryGenerate && widget.selected_packs && widget.selected_packs.length > 0 && (
            <button
              type="button"
              className="focus-ring mt-3 rounded-lg border border-rose-400 bg-well px-3 py-1.5 text-xs font-medium text-rose-900 disabled:opacity-50"
              disabled={busy}
              onClick={() => onRetryGenerate(widget.selected_packs!)}
            >
              {busy ? "Retrying…" : "Retry generate"}
            </button>
          )}
        </div>
      )}

      <div className="mt-4 max-h-64 overflow-y-auto rounded-xl border border-line bg-canvas/50 p-4">
        <Markdown text={widget.digest} />
      </div>
      <button
        type="button"
        className="focus-ring mt-2 rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:text-ink"
        onClick={() => setExpanded(true)}
      >
        Read full draft
      </button>

      {(widget.issues?.length ?? 0) > 0 && (
        <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-800">
            AI reviewer flagged {widget.issues!.length} issue
            {widget.issues!.length === 1 ? "" : "s"} — accept anyway, or revise the area
          </p>
          <ul className="mt-2 space-y-1.5">
            {widget.issues!.map((issue, i) => (
              <li key={i} className="break-words text-xs text-amber-900">
                <span className="font-mono text-[10px] uppercase">
                  [{issue.severity}] {issue.area.replaceAll("_", " ")}
                </span>{" "}
                {issue.note}
              </li>
            ))}
          </ul>
        </div>
      )}
      {expanded && (
        <DocModal
          title={`${widget.document} — draft`}
          text={widget.full_digest || widget.digest}
          onClose={() => setExpanded(false)}
        />
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          type="button"
          className="focus-ring rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-ink disabled:opacity-50"
          disabled={busy || generationBlocked}
          onClick={() => onAccept()}
        >
          {busy ? "Accepting…" : `Accept ${widget.document}`}
        </button>
      </div>

      {revisable.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <p className="text-sm font-medium text-ink">Send back for revision</p>
          <div className="mt-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end">
            <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-muted">
              Area
              <select
                className="focus-ring w-full min-w-0 rounded-lg border border-line bg-well px-3 py-2 text-sm text-ink"
                value={reviseArea}
                onChange={(e) => setReviseArea(e.target.value)}
              >
                <option value="">Select area…</option>
                {revisable.map((area) => (
                  <option key={area.key} value={area.key}>
                    {area.label} ({coverageStatusLabel(area.status)})
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="focus-ring w-full shrink-0 rounded-lg border border-line bg-glass px-4 py-2 text-sm text-ink disabled:opacity-50 sm:w-auto"
              disabled={busy || !reviseArea}
              onClick={() => onRevise(reviseArea, "")}
            >
              Revise
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
