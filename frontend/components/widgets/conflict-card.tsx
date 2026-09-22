import type { ConflictCardWidget } from "@/lib/widgets";

type Props = {
  widget: ConflictCardWidget;
  busy?: boolean;
  isActive?: boolean;
  hint?: string;
  recommendation?: { pick: "a" | "b"; why: string };
  onResolve?: (conflictId: string, winnerCardId: string) => void;
};

export function ConflictCard({
  widget,
  busy = false,
  isActive = true,
  hint,
  recommendation,
  onResolve,
}: Props) {
  return (
    <div className="rounded-xl border border-line bg-well p-3 text-sm shadow-sm">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
        Conflict detected
      </p>
      {recommendation?.why ? (
        <p className="mt-2 rounded-lg border border-line/80 bg-canvas/60 px-2.5 py-2 text-xs text-ink">
          <span className="font-medium text-muted">Recommendation:</span> Keep{" "}
          {recommendation.pick.toUpperCase()} — {recommendation.why}
        </p>
      ) : null}
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
      <p className="mt-2 text-ink">
        <span className="font-medium text-muted">A</span> {widget.statement_a}
      </p>
      <p className="mt-1.5 text-ink">
        <span className="font-medium text-muted">B</span> {widget.statement_b}
      </p>
      {isActive && onResolve ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="focus-ring rounded-lg border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
            disabled={busy}
            onClick={() => onResolve(widget.conflict_id, widget.card_a_id)}
          >
            Keep A
          </button>
          <button
            type="button"
            className="focus-ring rounded-lg border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
            disabled={busy}
            onClick={() => onResolve(widget.conflict_id, widget.card_b_id)}
          >
            Keep B
          </button>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">Resolved</p>
      )}
      <p className="mt-2 text-xs text-muted">
        Ask in chat if you want a recommendation — then pick Keep A or Keep B to confirm.
      </p>
    </div>
  );
}
