"use client";

import { Markdown } from "@/components/markdown";
import { TypewriterMarkdown } from "@/components/typewriter-text";
import { AcceptancePanel } from "@/components/widgets/acceptance-panel";
import { DeliverablePicker } from "@/components/widgets/deliverable-picker";
import { FactLog } from "@/components/widgets/fact-log";
import { OffTopicUpload } from "@/components/widgets/off-topic-upload";
import { PhaseRedirectSuggestion } from "@/components/widgets/phase-redirect-suggestion";
import { QuestionCard } from "@/components/widgets/question-card";
import type { Message, Upload } from "@/lib/api";
import { isWidget, hydrateQuestionCard } from "@/lib/widgets";

type Props = {
  message: Message;
  isLastQuestion?: boolean;
  isActiveGate?: boolean;
  busy?: boolean;
  /** Stream-aware typewriter for assistant prose (last streaming turn). */
  typewriter?: boolean;
  /** Current upload rows, to tell whether a flagged upload was already resolved. */
  uploads?: Upload[];
  /** True when this message carries the most recent phase_redirect_suggestion. */
  isLastRedirectSuggestion?: boolean;
  onSubmitQuestion?: (text: string) => void;
  onSkipQuestion?: () => void;
  onAcceptGate?: () => void;
  onReviseGate?: (area: string, content: string) => void;
  onSelectPacks?: (packIds: string[]) => void;
  onKeepUpload?: (uploadId: string) => void;
  onDiscardUpload?: (uploadId: string) => void;
  onGoToPlanning?: (planningArea: string | null) => void;
  onKeepHere?: (excerpt: string) => void;
};

export function ChatTurn({
  message,
  isLastQuestion = false,
  isActiveGate = false,
  busy = false,
  typewriter = false,
  uploads = [],
  isLastRedirectSuggestion = false,
  onSubmitQuestion,
  onSkipQuestion,
  onAcceptGate,
  onReviseGate,
  onSelectPacks,
  onKeepUpload,
  onDiscardUpload,
  onGoToPlanning,
  onKeepHere,
}: Props) {
  const widget = isWidget(message.widget) ? message.widget : null;
  const isUser = message.role === "user";
  const hasDecisionCard =
    widget?.type === "question_card" ||
    widget?.type === "deliverable_picker" ||
    widget?.type === "acceptance_panel" ||
    widget?.type === "conflict_card";

  if (isUser) {
    return (
      <div className="flex w-full justify-end">
        <div className="inline-block max-w-[min(85%,24rem)] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-sm text-accent-ink shadow-sm">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-w-0 w-full max-w-full space-y-2">
      {(message.content?.trim() || !hasDecisionCard) && (
        <div className="min-w-0 break-words text-sm text-ink">
          <p className="mb-1 text-[10px] font-medium tracking-[0.12em] uppercase text-muted">
            CrewLane
          </p>
          {message.content?.trim() ? (
            typewriter ? (
              <TypewriterMarkdown text={message.content} animate />
            ) : (
              <Markdown text={message.content} />
            )
          ) : null}
        </div>
      )}

      {widget?.type === "question_card" && (
        <QuestionCard
          widget={hydrateQuestionCard(widget)}
          isActive={isLastQuestion}
          onSubmit={onSubmitQuestion}
          onSkip={onSkipQuestion}
        />
      )}
      {widget?.type === "fact_log" && <FactLog widget={widget} />}
      {widget?.type === "conflict_card" && (
        <p className="mt-1 text-xs text-muted italic">
          Conflicting facts recorded — resolve using the card above the input.
        </p>
      )}
      {widget?.type === "deliverable_picker" && onSelectPacks && (
        <DeliverablePicker
          widget={widget}
          busy={busy}
          isActive={isActiveGate}
          onGenerate={onSelectPacks}
        />
      )}
      {widget?.type === "acceptance_panel" && onAcceptGate && onReviseGate && (
        <AcceptancePanel
          widget={widget}
          busy={busy}
          onAccept={onAcceptGate}
          onRevise={onReviseGate}
          onRetryGenerate={onSelectPacks}
        />
      )}
      {widget?.type === "gate_accepted" && (
        <p className="text-[11px] text-muted">
          Gate accepted · {widget.phase} · {widget.accepted_by}
        </p>
      )}
      {widget?.type === "off_topic_upload" && onKeepUpload && onDiscardUpload && (
        <OffTopicUpload
          widget={widget}
          resolved={
            uploads.find((u) => u.id === widget.upload_id)?.status !== "flagged"
          }
          onKeep={onKeepUpload}
          onDiscard={onDiscardUpload}
        />
      )}
      {widget?.type === "phase_redirect_suggestion" && onGoToPlanning && onKeepHere && (
        <PhaseRedirectSuggestion
          widget={widget}
          resolved={!isLastRedirectSuggestion}
          onGoToPlanning={onGoToPlanning}
          onKeepHere={onKeepHere}
        />
      )}
    </div>
  );
}
