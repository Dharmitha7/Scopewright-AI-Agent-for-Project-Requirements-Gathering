"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

type Props = {
  name: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DeleteProjectDialog({ name, busy, onCancel, onConfirm }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  const modal = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-project-title"
        className="relative w-full max-w-md rounded-2xl border border-line bg-well p-5 shadow-xl"
      >
        <h2 id="delete-project-title" className="text-base font-semibold text-ink">
          Delete project?
        </h2>
        <p className="mt-2 text-sm text-muted">
          <span className="font-medium text-ink">{name}</span> and all its messages, evidence,
          cards, and documents will be permanently removed. This cannot be undone.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            className="focus-ring rounded-lg border border-line px-3 py-1.5 text-sm text-ink"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="focus-ring rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Deleting…" : "Delete project"}
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}
