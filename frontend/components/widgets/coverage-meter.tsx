import { coverageStatusLabel, type CoverageMeterWidget } from "@/lib/widgets";

const DOT: Record<string, string> = {
  answered: "bg-accent",
  skipped: "border border-dashed border-muted bg-transparent",
  na: "bg-muted/40",
  pending: "border border-amber bg-transparent",
};

/** Areas touched = answered + skipped + na. */
export function coveragePercent(areas: CoverageMeterWidget["areas"]): number {
  const total = Math.max(areas.length, 1);
  const touched = areas.filter((a) => a.status !== "pending").length;
  return Math.round((100 * touched) / total);
}

export function CoverageMeter({ widget, title }: { widget: CoverageMeterWidget; title?: string }) {
  const pct = coveragePercent(widget.areas);
  const readiness = widget.readiness_score;
  const threshold = widget.readiness_threshold;
  const labelByKey = Object.fromEntries(widget.areas.map((a) => [a.key, a.label]));

  return (
    <div className="min-w-0">
      {title && (
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted">{title}</p>
      )}
      <div className={title ? "mt-3" : ""}>
        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          <span className="text-xs text-muted">Topics covered</span>
          <span className="text-xs font-semibold tabular-nums text-ink">{pct}%</span>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-canvas"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Topics covered ${pct} percent`}
        >
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
        {readiness != null && (
          <div className="mt-3">
            <div className="mb-1.5 flex items-baseline justify-between gap-2">
              <span className="text-xs text-muted">Ready to draft</span>
              <span className="text-xs font-semibold tabular-nums text-ink">
                {readiness}%
                {threshold != null ? ` / ${threshold}%` : ""}
              </span>
            </div>
            <div
              className="h-1.5 overflow-hidden rounded-full bg-canvas"
              role="progressbar"
              aria-valuenow={readiness}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Ready to draft ${readiness} percent`}
            >
              <div
                className={`h-full rounded-full transition-[width] duration-300 ${
                  threshold != null && readiness >= threshold ? "bg-accent" : "bg-amber-500"
                }`}
                style={{ width: `${Math.min(100, readiness)}%` }}
              />
            </div>
          </div>
        )}
      </div>
      <ul className="mt-3 flex flex-col gap-1.5">
        {widget.areas.map((area) => (
          <li
            key={area.key}
            className="flex items-start gap-2 rounded-lg border border-line bg-well/80 px-2.5 py-1.5"
            title={`${area.label}: ${coverageStatusLabel(area.status)}`}
          >
            <span
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[area.status] ?? DOT.pending}`}
            />
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-medium leading-snug text-ink">
                {area.label}
                {area.status === "skipped" ? " · skipped" : ""}
                {area.status === "na" ? " · n/a" : ""}
              </span>
              {area.hint && (
                <span className="mt-0.5 block text-[11px] leading-snug text-muted">{area.hint}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {(widget.readiness_blocking?.length ?? 0) > 0 && (
        <p className="mt-2 text-[11px] text-amber-800">
          Still thin:{" "}
          {widget.readiness_blocking!
            .map((k) => labelByKey[k] ?? k.replaceAll("_", " "))
            .join(", ")}
        </p>
      )}
    </div>
  );
}
