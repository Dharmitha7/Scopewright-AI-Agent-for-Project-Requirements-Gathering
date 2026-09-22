"use client";

import { useState } from "react";
import type { DeliverablePickerWidget } from "@/lib/widgets";

type Props = {
  widget: DeliverablePickerWidget;
  busy: boolean;
  isActive: boolean;
  /** Always separate packs (D84). */
  onGenerate: (packIds: string[]) => void;
};

export function DeliverablePicker({ widget, busy, isActive, onGenerate }: Props) {
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (key: string) => {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  return (
    <div className="mt-3 min-w-0 max-w-full rounded-xl border border-accent/20 bg-well p-4 shadow-sm">
      <p className="text-[11px] font-medium tracking-[0.12em] uppercase text-muted">
        Deliverables
      </p>
      <p className="mt-1 text-sm text-ink">
        Select one or more packs. Each pack is generated as its own document (D84).
      </p>
      <ul className="mt-3 min-w-0 space-y-2">
        {widget.packs.map((pack) => {
          const on = selected.includes(pack.key);
          return (
            <li key={pack.key} className="min-w-0">
              <label
                className={`flex min-w-0 cursor-pointer gap-2 rounded-xl border px-3 py-2 text-sm ${
                  on ? "border-accent/40 bg-accent/5" : "border-line bg-canvas/40"
                } ${!isActive ? "opacity-60" : ""}`}
              >
                <input
                  type="checkbox"
                  className="mt-1 shrink-0"
                  checked={on}
                  disabled={!isActive || busy}
                  onChange={() => toggle(pack.key)}
                />
                <span className="min-w-0 flex-1">
                  <span className="block break-words font-medium text-ink">{pack.title}</span>
                  <span className="mt-0.5 block break-words text-xs text-muted">{pack.purpose}</span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        className="focus-ring mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-ink disabled:opacity-50"
        disabled={!isActive || busy || selected.length === 0}
        onClick={() => onGenerate(selected)}
      >
        {busy ? "Generating…" : "Generate selected"}
      </button>
    </div>
  );
}
