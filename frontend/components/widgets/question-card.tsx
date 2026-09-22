import { useMemo, useState } from "react";
import type { QuestionCardWidget } from "@/lib/widgets";

function isOtherOption(option: string): boolean {
  return option.trim().toLowerCase() === "other";
}

export function QuestionCard({
  widget,
  isActive = false,
  onSubmit,
  onSkip,
}: {
  widget: QuestionCardWidget;
  isActive?: boolean;
  onSubmit?: (text: string) => void;
  onSkip?: () => void;
}) {
  const prompts = useMemo(
    () => (widget.prompts?.length ? widget.prompts : [widget.prompt]),
    [widget.prompt, widget.prompts],
  );
  const confirm = widget.mode === "confirm";
  const options = widget.options ?? [];
  const selectionMode = widget.selection_mode ?? (confirm ? "single" : "multi");
  const [selectedByPrompt, setSelectedByPrompt] = useState<Record<number, string[]>>({});
  const [otherByPrompt, setOtherByPrompt] = useState<Record<number, string>>({});

  const hasSelections = useMemo(
    () =>
      prompts.some((_, idx) => {
        const selected = selectedByPrompt[idx] ?? [];
        const otherText = (otherByPrompt[idx] ?? "").trim();
        if (selected.some((opt) => !isOtherOption(opt))) return true;
        return selected.some(isOtherOption) && otherText.length > 0;
      }),
    [otherByPrompt, prompts, selectedByPrompt],
  );

  const toggleOption = (promptIdx: number, option: string) => {
    setSelectedByPrompt((prev) => {
      const current = prev[promptIdx] ?? [];
      if (selectionMode === "single") {
        return { ...prev, [promptIdx]: current[0] === option ? [] : [option] };
      }
      const exists = current.includes(option);
      return {
        ...prev,
        [promptIdx]: exists ? current.filter((item) => item !== option) : [...current, option],
      };
    });
    if (selectionMode === "single" && !isOtherOption(option)) {
      setOtherByPrompt((prev) => ({ ...prev, [promptIdx]: "" }));
    }
  };

  const submitSelections = () => {
    const lines = prompts.flatMap((prompt, idx) => {
      const selected = selectedByPrompt[idx] ?? [];
      const normalized = selected
        .map((opt) => {
          if (!isOtherOption(opt)) return opt;
          const otherText = (otherByPrompt[idx] ?? "").trim();
          return otherText || null;
        })
        .filter((value): value is string => Boolean(value));
      if (normalized.length === 0) return [];
      const answer = normalized.join(", ");
      return prompts.length === 1 ? [answer] : [`${idx + 1}. ${prompt}\n${answer}`];
    });
    if (lines.length === 0) return;
    onSubmit?.(lines.join("\n\n"));
  };

  return (
    <div
      className={`mt-2 rounded-xl border p-3 ${
        confirm ? "border-accent/30 bg-accent/5" : "border-line bg-well/80"
      }`}
    >
      <p className="text-[10px] font-medium tracking-[0.12em] uppercase text-muted">
        {widget.purpose_label}
        {confirm ? " · confirm" : ""}
      </p>
      {widget.purpose_hint && (
        <p className="mt-0.5 text-[11px] leading-snug text-muted">{widget.purpose_hint}</p>
      )}
      {confirm && widget.known && widget.known.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted">
          {widget.known.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
      {prompts.map((prompt, i) => (
        <div key={prompt} className="mt-2">
          {prompts.length === 1 ? (
            <p className="text-sm">{prompt}</p>
          ) : (
            <p className="text-sm">
              <span className="mr-1 font-medium text-muted">{i + 1}.</span>
              {prompt}
            </p>
          )}
          {isActive && options[i] && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {options[i]!.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  className={`focus-ring rounded-full border px-3 py-1 text-xs transition-colors ${
                    (selectedByPrompt[i] ?? []).includes(opt)
                      ? "border-accent bg-accent text-accent-ink"
                      : "border-line bg-well text-ink hover:border-accent/40"
                  }`}
                  onClick={() => toggleOption(i, opt)}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
          {isActive && options[i]?.some(isOtherOption) && (selectedByPrompt[i] ?? []).some(isOtherOption) && (
            <input
              type="text"
              className="focus-ring mt-2 w-full rounded-lg border border-line bg-well px-3 py-2 text-sm focus:outline-none"
              placeholder="Add your custom answer"
              value={otherByPrompt[i] ?? ""}
              onChange={(e) =>
                setOtherByPrompt((prev) => ({
                  ...prev,
                  [i]: e.target.value,
                }))
              }
            />
          )}
        </div>
      ))}
      {isActive && (
        <>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="focus-ring rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink disabled:opacity-50"
              disabled={!hasSelections}
              onClick={submitSelections}
            >
              Submit answers
            </button>
            {onSkip && (
              <button
                type="button"
                className="focus-ring rounded-lg border border-line bg-well px-3 py-1.5 text-xs text-muted hover:border-accent/40 hover:text-ink"
                onClick={onSkip}
              >
                Skip for now
              </button>
            )}
            <p className="text-[11px] text-muted">
              {selectionMode === "multi" ? "Select all that apply, then submit once." : "Choose one answer, then submit."}
            </p>
          </div>
          <p className="mt-2 text-[11px] text-muted">Or type your own answer below</p>
        </>
      )}
      {!isActive && (
        <p className="mt-2 text-[11px] text-muted/50 italic">answered</p>
      )}
    </div>
  );
}
