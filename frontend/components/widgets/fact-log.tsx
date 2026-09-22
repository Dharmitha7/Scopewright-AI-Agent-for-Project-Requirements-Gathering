import type { FactLogWidget } from "@/lib/widgets";

export function FactLog({ widget }: { widget: FactLogWidget }) {
  if (widget.facts.length === 0) return null;
  return (
    <details className="mt-2 rounded-xl border border-line bg-well/80 px-3 py-2">
      <summary className="cursor-pointer text-xs text-muted">
        {widget.facts.length === 1 ? "1 recorded fact" : `${widget.facts.length} recorded facts`}
        {widget.area ? ` · ${widget.area.replaceAll("_", " ")}` : ""}
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted">
        {widget.facts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>
    </details>
  );
}
