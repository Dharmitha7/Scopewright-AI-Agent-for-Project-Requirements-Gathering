import type { Message } from "@/lib/api";
import { COVERAGE_TEMPLATES, lookupCoverageArea } from "@/lib/coverage-areas";

export type QuestionCardWidget = {
  type: "question_card";
  purpose: string;
  purpose_label: string;
  purpose_hint?: string;
  prompt: string;
  prompts?: string[];
  options?: (string[] | null)[];
  mode?: "ask" | "confirm";
  known?: string[];
  selection_mode?: "single" | "multi";
};

export type CoverageArea = {
  key: string;
  label: string;
  hint?: string;
  status: "pending" | "answered" | "skipped" | "na";
};

export type CoverageMeterWidget = {
  type: "coverage_meter";
  phase: string;
  areas: CoverageArea[];
  readiness_score?: number;
  readiness_threshold?: number;
  readiness_blocking?: string[];
};

export type FactLogWidget = {
  type: "fact_log";
  area: string;
  facts: string[];
  source_message_id: string;
};

export type ReviewIssue = {
  severity: "high" | "medium" | "low";
  area: string;
  note: string;
};

export type AcceptancePanelWidget = {
  type: "acceptance_panel";
  phase: string;
  document: string;
  coverage: Record<string, string>;
  digest: string;
  /** Complete draft for Expand; falls back to digest when absent. */
  full_digest?: string;
  issues?: ReviewIssue[];
  selected_packs?: string[];
  pack_mode?: "separate";
  /** Pack keys whose generation failed — Accept must stay disabled. */
  failed_packs?: string[];
};

export type DeliverablePickerWidget = {
  type: "deliverable_picker";
  phase: string;
  document: string;
  packs: { key: string; title: string; purpose: string }[];
  coverage: Record<string, string>;
};

export type GateAcceptedWidget = {
  type: "gate_accepted";
  phase: string;
  accepted_by: string;
};

export type ConflictCardWidget = {
  type: "conflict_card";
  conflict_id: string;
  card_a_id: string;
  card_b_id: string;
  statement_a: string;
  statement_b: string;
};

export type FeasibilityReportWidget = {
  type: "feasibility_report";
  query: string;
  summary: string;
  sources: { title: string; link: string; snippet: string }[];
};

export type OffTopicUploadWidget = {
  type: "off_topic_upload";
  upload_id: string;
  filename: string;
  chunk_count: number;
};

export type PhaseRedirectSuggestionWidget = {
  type: "phase_redirect_suggestion";
  planning_area: string | null;
  excerpt: string;
  reason: string;
};

export type MessageWidget =
  | QuestionCardWidget
  | CoverageMeterWidget
  | FactLogWidget
  | AcceptancePanelWidget
  | DeliverablePickerWidget
  | GateAcceptedWidget
  | ConflictCardWidget
  | FeasibilityReportWidget
  | OffTopicUploadWidget
  | PhaseRedirectSuggestionWidget;

export function isWidget(widget: unknown): widget is MessageWidget {
  return typeof widget === "object" && widget !== null && "type" in widget;
}

export function findLastWidget<T extends MessageWidget["type"]>(
  messages: Message[],
  kind: T,
): Extract<MessageWidget, { type: T }> | null {
  const index = findLastWidgetIndex(messages, kind);
  return index === -1 ? null : (messages[index].widget as Extract<MessageWidget, { type: T }>);
}

export function findLastWidgetIndex(messages: Message[], kind: MessageWidget["type"]): number {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const widget = messages[i].widget;
    if (isWidget(widget) && widget.type === kind) {
      return i;
    }
  }
  return -1;
}

export type SessionMode = "interview" | "gate" | "complete" | "idle";

export function sessionMode(messages: Message[], phase: string): SessionMode {
  // D83: phase "done" stays chat-enabled (free-form); not a hard stop.
  if (phase === "done") return "interview";

  const gateIdx = findLastWidgetIndex(messages, "gate_accepted");
  const panelIdx = findLastWidgetIndex(messages, "acceptance_panel");
  const pickerIdx = findLastWidgetIndex(messages, "deliverable_picker");
  const questionIdx = findLastWidgetIndex(messages, "question_card");
  const decisionIdx = Math.max(panelIdx, pickerIdx);

  if (decisionIdx !== -1 && decisionIdx > gateIdx && decisionIdx > questionIdx) {
    return "gate";
  }

  if (questionIdx !== -1) {
    return "interview";
  }

  return "idle";
}

export function phaseLabel(phase: string): string {
  switch (phase) {
    case "planning":
      return "Planning";
    case "requirements":
      return "Requirements";
    case "done":
      return "Complete";
    default:
      return phase;
  }
}

export function coverageStatusLabel(status: string): string {
  switch (status) {
    case "answered":
      return "answered";
    case "skipped":
      return "skipped";
    case "na":
      return "n/a";
    case "pending":
      return "not yet";
    default:
      return status;
  }
}

/** Stored widgets freeze labels at write time — merge current template metadata for display. */
export function hydrateCoverageMeter(widget: CoverageMeterWidget): CoverageMeterWidget {
  const template = COVERAGE_TEMPLATES[widget.phase];
  if (!template) return widget;
  const byKey = Object.fromEntries(template.map((a) => [a.key, a]));
  return {
    ...widget,
    areas: widget.areas.map((area) => ({
      ...area,
      label: byKey[area.key]?.label ?? area.label,
      hint: byKey[area.key]?.hint ?? area.hint,
    })),
  };
}

export function hydrateQuestionCard(widget: QuestionCardWidget): QuestionCardWidget {
  const meta = lookupCoverageArea(widget.purpose);
  if (!meta) return widget;
  return {
    ...widget,
    purpose_label: meta.label,
    purpose_hint: meta.hint,
  };
}
