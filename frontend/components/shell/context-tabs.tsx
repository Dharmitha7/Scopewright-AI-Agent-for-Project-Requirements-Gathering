"use client";

export type WorkspaceTab = "artifacts" | "coverage" | "audit" | "knowledge";

type Props = {
  tab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  labels: Record<WorkspaceTab, string>;
};

/**
 * One row, panel-width: pills share the row so there is no empty gap after
 * Knowledge. Panel width is sized to this row (see AppShell).
 */
export function ContextTabs({ tab, onTabChange, labels }: Props) {
  const tabs = (["artifacts", "coverage", "audit", "knowledge"] as const).map((key) => ({
    key,
    label: labels[key],
  }));

  return (
    <div
      className="flex w-full flex-nowrap items-center gap-1 overflow-x-hidden bg-transparent py-2.5 pl-2 pr-10"
      aria-label="Context tabs"
    >
      {tabs.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          title={label}
          className={`focus-ring min-w-0 flex-1 truncate rounded-full px-1.5 py-1.5 text-center text-[11px] font-medium ${
            tab === key
              ? "bg-accent text-accent-ink"
              : "border border-line bg-well/70 text-muted hover:text-ink"
          }`}
          onClick={() => onTabChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
