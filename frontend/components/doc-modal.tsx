"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";
import { Markdown } from "@/components/markdown";

// Full-width reading view: reviewing a Charter/SRS in a narrow rail is not a
// review (UX audit finding). Esc or backdrop click closes. Portaled to body so
// overflow:hidden panels cannot clip the dialog.
export function DocModal({
  title,
  text,
  onClose,
}: {
  title: string;
  text: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const modal = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl border border-line bg-well shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-3">
          <p className="text-[11px] font-medium tracking-[0.12em] uppercase text-muted">{title}</p>
          <button
            type="button"
            className="focus-ring rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink"
            onClick={onClose}
            title="Close (Esc)"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5 text-ink">
          <Markdown text={text} />
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}
