"use client";

import { useState } from "react";
import type { OffTopicUploadWidget } from "@/lib/widgets";

export function OffTopicUpload({
  widget,
  resolved,
  onKeep,
  onDiscard,
}: {
  widget: OffTopicUploadWidget;
  /** True once the upload has moved past "flagged" (kept or discarded elsewhere). */
  resolved: boolean;
  onKeep: (uploadId: string) => void;
  onDiscard: (uploadId: string) => void;
}) {
  const [busy, setBusy] = useState<"keep" | "discard" | null>(null);

  if (resolved) {
    return (
      <p className="mt-1 text-xs text-muted italic">Reviewed — see Evidence for the outcome.</p>
    );
  }

  return (
    <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5">
      <p className="text-xs text-amber-900">
        <span className="font-medium">{widget.filename}</span> did not match this project&apos;s
        scope in any of its {widget.chunk_count} chunk{widget.chunk_count === 1 ? "" : "s"} —
        nothing was recorded from it.
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={busy !== null}
          className="rounded-lg border border-amber-300 bg-white px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-50"
          onClick={() => {
            setBusy("keep");
            onKeep(widget.upload_id);
          }}
        >
          {busy === "keep" ? "Keeping…" : "Keep anyway"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          className="rounded-lg border border-line bg-white px-2.5 py-1 text-xs font-medium text-muted hover:bg-well disabled:opacity-50"
          onClick={() => {
            setBusy("discard");
            onDiscard(widget.upload_id);
          }}
        >
          {busy === "discard" ? "Discarding…" : "Discard"}
        </button>
      </div>
    </div>
  );
}
