"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { AppShell, ICON_BTN, RightPanelMenu, useShellChrome } from "@/components/shell/app-shell";
import { SidebarToggleIcon } from "@/components/shell/sidebar-toggle-icon";
import type { WorkspaceTab } from "@/components/shell/context-tabs";
import { EvidencePreviewModal } from "@/components/shell/evidence-preview";
import { AuditTrail } from "@/components/widgets/audit-trail";
import { CardList } from "@/components/widgets/card-list";
import { ChatTurn } from "@/components/widgets/chat-turn";
import { ConflictCard } from "@/components/widgets/conflict-card";
import { CoverageMeter } from "@/components/widgets/coverage-meter";
import { DocumentView } from "@/components/widgets/document-view";
import {
  IngestCompleteNotice,
  IngestProgressBanner,
  UploadStatusBadge,
  composerIngestPill,
  summarizeIngestBatch,
} from "@/components/widgets/upload-status";
import {
  api,
  ApiError,
  type Account,
  type AuditEvent,
  type Card,
  type ChatPhaseTab,
  type ChatState,
  type ConflictItem,
  type ConflictAdvice,
  type ConflictListResponse,
  type Message,
  type Project,
  type Snapshot,
  type Upload,
} from "@/lib/api";
import { pendingUploads as filterPendingUploads, isUploadPending } from "@/lib/uploads";
import {
  findLastWidget,
  findLastWidgetIndex,
  hydrateCoverageMeter,
  phaseLabel,
  sessionMode,
  type ConflictCardWidget,
} from "@/lib/widgets";
import { streamProjectMessage } from "@/lib/stream";
import { useAutoResizeTextarea } from "@/lib/use-auto-resize-textarea";

function liveChatTab(phase: string): ChatPhaseTab {
  return phase === "planning" ? "planning" : "requirements";
}

function auditDetail(event: AuditEvent): string {
  const d = event.detail;
  const parts: string[] = [];

  if (typeof d.phase === "string" && d.phase) parts.push(d.phase);
  if (typeof d.area === "string" && d.area) parts.push(d.area.replaceAll("_", " "));
  if (typeof d.name === "string" && d.name) parts.push(d.name);
  if (typeof d.from === "string" && typeof d.to === "string") {
    parts.push(`${d.from} → ${d.to}`);
  } else {
    if (typeof d.from === "string" && d.from) parts.push(d.from);
    if (typeof d.to === "string" && d.to) parts.push(d.to);
  }
  if (typeof d.filename === "string" && d.filename) parts.push(d.filename);
  if (typeof d.url === "string" && d.url) parts.push(d.url);
  if (typeof d.snippet === "string" && d.snippet) {
    parts.push(d.snippet.length > 120 ? `${d.snippet.slice(0, 120)}…` : d.snippet);
  }
  if (typeof d.note === "string" && d.note) {
    parts.push(d.note.length > 120 ? `${d.note.slice(0, 120)}…` : d.note);
  }
  if (typeof d.new_body === "string" && d.new_body) {
    parts.push(d.new_body.length > 120 ? `${d.new_body.slice(0, 120)}…` : d.new_body);
  }
  if (typeof d.card_id === "string" && d.card_id) parts.push(`card ${d.card_id.slice(0, 8)}`);
  if (typeof d.winner_card_id === "string" && d.winner_card_id) {
    parts.push(`kept ${d.winner_card_id.slice(0, 8)}`);
  }

  return parts.join(" · ");
}

function applyIngestCompleteNotice(
  uploadRows: Upload[],
  hadPendingRef: React.MutableRefObject<boolean>,
  setNotice: (msg: string) => void,
) {
  const stillPending = uploadRows.some((u) => isUploadPending(u.status));
  if (hadPendingRef.current && !stillPending) {
    const summary = summarizeIngestBatch(uploadRows);
    if (summary) setNotice(summary);
  }
  hadPendingRef.current = stillPending;
}

const FILE_ACCEPT =
  ".txt,.md,.pdf,.docx,.xlsx,.pptx,.csv,.vtt,.srt,.html,.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.m4a,.mp4,.webm,.ogg,.flac";

function conflictToWidget(c: ConflictItem): ConflictCardWidget {
  return {
    type: "conflict_card",
    conflict_id: c.id,
    card_a_id: c.card_a.id,
    card_b_id: c.card_b.id,
    statement_a: c.card_a.body,
    statement_b: c.card_b.body,
  };
}

function applyConflictList(data: ConflictListResponse, setConflicts: (items: ConflictItem[]) => void) {
  setConflicts(data.items);
}

export default function ProjectWorkspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [account, setAccount] = useState<Account | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [conflictAdvice, setConflictAdvice] = useState<ConflictAdvice | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const [tab, setTab] = useState<WorkspaceTab>("artifacts");
  const [chatTab, setChatTab] = useState<ChatPhaseTab>("planning");
  const [chatState, setChatState] = useState<ChatState | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [recordError, setRecordError] = useState("");
  const [ingestNotice, setIngestNotice] = useState("");
  const [previewUpload, setPreviewUpload] = useState<Upload | null>(null);
  const chatTabRef = useRef(chatTab);
  useEffect(() => {
    chatTabRef.current = chatTab;
  }, [chatTab]);
  const hadPendingUploadsRef = useRef(false);
  const chatScroll = useRef<HTMLDivElement>(null);
  const pinnedToBottom = useRef(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const refreshShell = useCallback(async () => {
    const [me, list] = await Promise.all([api.me(), api.listProjects()]);
    setAccount(me);
    setProjects(list);
  }, []);

  const refreshWorkspace = useCallback(async (phaseTab?: ChatPhaseTab, init = false) => {
    const found = await api.getProject(id);
    setProject(found);
    const tabForMessages =
      phaseTab ?? (init ? liveChatTab(found.phase) : chatTabRef.current);
    if (init || phaseTab) setChatTab(tabForMessages);

    const [messagesResult, chatStateResult, cardsResult, snapshotsResult, uploadsResult, conflictsResult, auditResult] =
      await Promise.allSettled([
        api.listMessages(id, { phase: tabForMessages }),
        api.getChatState(id, tabForMessages),
        api.listCards(id),
        api.listSnapshots(id),
        api.listUploads(id),
        api.listConflicts(id),
        api.listAudit(id),
      ]);

    const failed: string[] = [];
    if (messagesResult.status === "fulfilled") setMessages(messagesResult.value);
    else failed.push("messages");
    if (chatStateResult.status === "fulfilled") setChatState(chatStateResult.value);
    else failed.push("chat");
    if (cardsResult.status === "fulfilled") setCards(cardsResult.value);
    else failed.push("cards");
    if (snapshotsResult.status === "fulfilled") setSnapshots(snapshotsResult.value);
    else failed.push("documents");
    if (uploadsResult.status === "fulfilled") {
      applyIngestCompleteNotice(uploadsResult.value, hadPendingUploadsRef, setIngestNotice);
      setUploads(uploadsResult.value);
    } else failed.push("evidence");
    if (conflictsResult.status === "fulfilled") {
      applyConflictList(conflictsResult.value, setConflicts);
    } else failed.push("conflicts");
    if (auditResult.status === "fulfilled") setAuditEvents(auditResult.value);
    else failed.push("audit");

    setError(failed.length ? `Couldn't load: ${failed.join(", ")}.` : "");
    return found;
  }, [id]);

  const loadWorkspace = useCallback(
    (onDone?: () => void) => {
      let cancelled = false;
      refreshWorkspace(undefined, true)
        .catch((err) => {
          if (cancelled) return;
          if (err instanceof ApiError && err.status === 404) setMissing(true);
          setError(err instanceof Error ? err.message : "could not load project");
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
            onDone?.();
          }
        });
      return () => {
        cancelled = true;
      };
    },
    [refreshWorkspace],
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- shell account/projects bootstrap
    void refreshShell().catch(() => setAccount(null));
  }, [refreshShell]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- workspace bootstrap
    return loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    const el = chatScroll.current;
    if (el && pinnedToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const activeConflict = conflicts[0] ?? null;

  useEffect(() => {
    if (!activeConflict) return;
    let cancelled = false;
    void api
      .getConflictAdvice(id, activeConflict.id)
      .then((advice) => {
        if (!cancelled) setConflictAdvice(advice);
      })
      .catch(() => {
        if (!cancelled) setConflictAdvice(null);
      });
    return () => {
      cancelled = true;
    };
  }, [id, activeConflict?.id]);

  const tabWritable =
    chatState?.writable ?? (project ? liveChatTab(project.phase) === chatTab : false);
  const mode = project
    ? tabWritable
      ? sessionMode(messages, project.phase)
      : "idle"
    : "idle";
  const lastQuestionIdx = findLastWidgetIndex(messages, "question_card");
  const lastRedirectSuggestionIdx = findLastWidgetIndex(messages, "phase_redirect_suggestion");
  const coverageRaw = findLastWidget(messages, "coverage_meter");
  const coverage = coverageRaw ? hydrateCoverageMeter(coverageRaw) : null;
  const lastPickerIdx = findLastWidgetIndex(messages, "deliverable_picker");
  const lastPanelIdx = findLastWidgetIndex(messages, "acceptance_panel");
  const lastAcceptance = findLastWidget(messages, "acceptance_panel");
  const gateGenFailed =
    !!lastAcceptance &&
    lastAcceptance.type === "acceptance_panel" &&
    (lastAcceptance.failed_packs?.length ?? 0) > 0;
  const activeGateWidgetIdx = Math.max(lastPickerIdx, lastPanelIdx);

  const send = async (body: {
    content?: string;
    skipped?: boolean;
    bound_to_question?: boolean;
    skip_redirect_check?: boolean;
  }) => {
    const filesToUpload = [...attachedFiles];
    setAttachedFiles([]);
    setBusy(true);
    setStreaming(true);
    setError("");
    const userText = body.skipped ? "Skip for now" : (body.content ?? "").trim();
    const optimisticUser: Message = {
      id: `local-${Date.now()}`,
      role: "user",
      content: userText || (filesToUpload.length ? `[${filesToUpload.length} file(s) attached]` : ""),
      widget: null,
      phase: chatTab,
      thread_key: chatState?.thread_key ?? "",
      created_at: new Date().toISOString(),
    };
    if (userText || filesToUpload.length) {
      setMessages((prev) => [...prev, optimisticUser]);
    }
    const draftBeforeSend = draft;
    setDraft(""); // clear on send, not on reply - the box shouldn't sit full while "thinking"
    try {
      for (const file of filesToUpload) {
        await api.uploadFile(id, file);
      }
      if (filesToUpload.length > 0) {
        setUploads(await api.listUploads(id));
      }
      if (!userText && !body.skipped && filesToUpload.length > 0) {
        setMessages((prev) => prev.filter((m) => !m.id.startsWith("local-")));
        return;
      }
      const bindToQuestion =
        body.bound_to_question ??
        (mode === "interview" &&
          lastQuestionIdx >= 0 &&
          conflicts.length === 0 &&
          !body.skipped &&
          !!userText &&
          !userText.endsWith("?"));
      await streamProjectMessage(
        id,
        { ...body, bound_to_question: bindToQuestion, tab: chatTab },
        {
          onMessage: (message) => {
            setMessages((prev) => {
              const withoutOptimistic = prev.filter((m) => !m.id.startsWith("local-"));
              const ids = new Set(withoutOptimistic.map((m) => m.id));
              if (ids.has(message.id)) {
                return withoutOptimistic.map((m) => (m.id === message.id ? message : m));
              }
              return [...withoutOptimistic, message];
            });
          },
          onError: (message) => setError(message),
        },
      );
      setCards(await api.listCards(id));
      applyConflictList(await api.listConflicts(id), setConflicts);
      setAuditEvents(await api.listAudit(id));
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.id.startsWith("local-")));
      setDraft(draftBeforeSend); // don't lose what they typed on a failed send
      setError(err instanceof Error ? err.message : "could not send");
    } finally {
      setBusy(false);
      setStreaming(false);
    }
  };

  const handleQuestionSubmit = (text: string) => {
    if (!busy) void send({ content: text, bound_to_question: true });
  };

  const handleSkipQuestion = () => {
    if (!busy) void send({ skipped: true, bound_to_question: true });
  };

  const acceptGate = async () => {
    setBusy(true);
    setError("");
    try {
      const thread = await api.postGate(id, { action: "accept", tab: chatTab });
      if (chatTab === "planning") {
        setChatTab("requirements");
        await refreshWorkspace("requirements");
      } else {
        setMessages(thread);
        await refreshWorkspace(chatTab);
      }
      setAuditEvents(await api.listAudit(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not accept gate");
    } finally {
      setBusy(false);
    }
  };

  const reviseGate = async (area: string, content: string) => {
    setBusy(true);
    setError("");
    try {
      const thread = await api.postGate(id, { action: "revise", area, content, tab: chatTab });
      setMessages(thread);
      setAuditEvents(await api.listAudit(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not revise gate");
    } finally {
      setBusy(false);
    }
  };

  const selectPacks = async (packIds: string[]) => {
    setBusy(true);
    setError("");
    try {
      const thread = await api.postGate(id, {
        action: "select_packs",
        pack_ids: packIds,
        pack_mode: "separate",
        tab: chatTab,
      });
      setMessages(thread);
      setTab("artifacts");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not generate deliverables");
    } finally {
      setBusy(false);
    }
  };

  const redraftRequirements = async () => {
    setBusy(true);
    setError("");
    try {
      const thread = await api.postGate(id, { action: "redraft", tab: "requirements" });
      setMessages(thread);
      await refreshWorkspace("requirements");
      setTab("artifacts");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not start redraft");
    } finally {
      setBusy(false);
    }
  };

  const switchChatTab = async (key: ChatPhaseTab) => {
    setChatTab(key);
    setError("");
    try {
      const [msgs, state] = await Promise.all([
        api.listMessages(id, { phase: key }),
        api.getChatState(id, key),
      ]);
      setMessages(msgs);
      setChatState(state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not load tab");
    }
  };

  const queueFiles = (files: FileList | File[]) => {
    const next = Array.from(files);
    if (next.length === 0) return;
    setAttachedFiles((prev) => [...prev, ...next]);
  };

  const resolveConflict = async (conflictId: string, winnerCardId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.resolveConflict(id, conflictId, winnerCardId);
      const remaining = await api.listConflicts(id);
      applyConflictList(remaining, setConflicts);
      setCards(await api.listCards(id));
      if (remaining.items.length === 0) {
        await send({ content: "Ready to continue." });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not resolve conflict");
    } finally {
      setBusy(false);
    }
  };

  const editCard = async (cardId: string, body: string) => {
    setBusy(true);
    setError("");
    try {
      await api.updateCard(id, cardId, body);
      setCards(await api.listCards(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not edit card");
    } finally {
      setBusy(false);
    }
  };

  const retireCard = async (cardId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.retireCard(id, cardId);
      setCards(await api.listCards(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not strike card");
    } finally {
      setBusy(false);
    }
  };

  const addLink = async (url: string) => {
    setBusy(true);
    setError("");
    try {
      await api.ingestLink(id, url);
      setUploads(await api.listUploads(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not fetch link");
    } finally {
      setBusy(false);
    }
  };

  const keepFlaggedUpload = async (uploadId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.keepUpload(id, uploadId);
      await refreshWorkspace(chatTab);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not keep upload");
    } finally {
      setBusy(false);
    }
  };

  const discardFlaggedUpload = async (uploadId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.discardUpload(id, uploadId);
      await refreshWorkspace(chatTab);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not discard upload");
    } finally {
      setBusy(false);
    }
  };

  const goToPlanning = async (planningArea: string | null) => {
    setBusy(true);
    setError("");
    try {
      await api.postGate(id, {
        action: "planning_redraft",
        tab: "planning",
        area: planningArea ?? undefined,
      });
      await refreshWorkspace("planning");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not reopen Planning");
    } finally {
      setBusy(false);
    }
  };

  const keepHere = async (excerpt: string) => {
    if (!busy) await send({ content: excerpt, skip_redirect_check: true });
  };

  const transcribeDictation = async (file: File) => {
    setTranscribing(true);
    setRecordError("");
    try {
      const { text } = await api.transcribe(id, file);
      const trimmed = text.trim();
      if (trimmed) {
        setDraft((prev) => (prev.trim() ? `${prev.trimEnd()} ${trimmed}` : trimmed));
        textareaRef.current?.focus();
      }
    } catch (err) {
      setRecordError(err instanceof Error ? err.message : "could not transcribe");
    } finally {
      setTranscribing(false);
    }
  };

  const startRecording = async () => {
    setRecordError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const stamp = new Date().toISOString().replaceAll(":", "-").slice(0, 19);
        const file = new File([blob], `recording-${stamp}.webm`, { type: blob.type });
        void transcribeDictation(file);
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setRecordError("Microphone unavailable — check browser permissions.");
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files?.length) queueFiles(e.dataTransfer.files);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData("text/plain");
    if (text.match(/^https?:\/\//)) {
      e.preventDefault();
      if (confirm(`Fetch and ingest this link?\n${text}`)) {
        void addLink(text);
      } else {
        setDraft((prev) => prev + text);
      }
    }
  };

  // While ingest is running, poll upload status only. Replacing the full
  // message thread every 3s caused chat scroll jank; cards/messages refresh
  // once when all uploads finish processing (refreshWorkspace). "flagged" is
  // a finished-processing state too (D86) - the job is done, only a human
  // keep/discard decision is pending, not more background work - so it must
  // count as "finished" here or the poll runs forever without ever fetching
  // the off_topic_upload chat message that a flagged upload posts.
  const hasPendingUploads = uploads.some(
    (u) => u.status === "queued" || u.status === "processing",
  );

  useEffect(() => {
    if (!project || !hasPendingUploads) return;
    const timer = setInterval(() => {
      void api.listUploads(id).then((uploadRows) => {
        applyIngestCompleteNotice(uploadRows, hadPendingUploadsRef, setIngestNotice);
        setUploads(uploadRows);
        if (uploadRows.every((u) => u.status !== "queued" && u.status !== "processing")) {
          void refreshWorkspace();
        }
      });
    }, 3000);
    return () => clearInterval(timer);
  }, [id, project, hasPendingUploads, refreshWorkspace]);

  const charter = [...snapshots].reverse().find((s) => s.phase === "planning");
  const srs = [...snapshots].reverse().find((s) => s.phase === "requirements");
  const hasOpenConflicts = conflicts.length > 0;
  const pendingUploads = filterPendingUploads(uploads);
  const canAnswer =
    tabWritable &&
    !busy &&
    pendingUploads.length === 0 &&
    (hasOpenConflicts || mode === "interview" || mode === "gate");
  const failedUploads = uploads.filter((u) => u.status === "failed");
  const flaggedUploads = uploads.filter((u) => u.status === "flagged");
  const reading = messages.length === 0 && pendingUploads.length > 0;
  const showCenteredEmpty =
    tabWritable &&
    messages.length === 0 &&
    !reading &&
    failedUploads.length === 0 &&
    !hasOpenConflicts &&
    uploads.length === 0;

  const tabLabels: Record<WorkspaceTab, string> = {
    artifacts: "Artifacts",
    coverage: "Checklist",
    audit: "Audit",
    knowledge: "Knowledge",
  };

  const onWorkspaceTab = (key: WorkspaceTab) => {
    setTab(key);
    if (key === "audit") void api.listAudit(id).then(setAuditEvents);
  };

  const lastMsg = messages[messages.length - 1];
  const typewriterId =
    streaming && lastMsg?.role === "assistant" ? lastMsg.id : null;

  if (!account) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <p className="text-sm text-muted">
          {loading ? "Loading…" : (
            <>
              Sign in required.{" "}
              <Link href="/" className="text-accent underline">
                Go home
              </Link>
            </>
          )}
        </p>
      </div>
    );
  }

  const rightPanel = project && !loading && !missing ? (
    <div className="sidebar-scroll min-h-0 flex-1 overflow-y-auto p-3">
      <div className="space-y-4">
        {tab === "artifacts" && (
          <>
            {charter || srs ? (
              <div className="space-y-3">
                {charter && (
                  <DocumentView projectId={id} projectName={project.name} snapshot={charter} />
                )}
                {srs && <DocumentView projectId={id} projectName={project.name} snapshot={srs} />}
              </div>
            ) : (
              <p className="text-xs text-muted">
                Accepted Charter and Requirements appear here after each gate.
              </p>
            )}
            <div className="border-t border-line pt-4">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Evidence</h2>
              <ul className="mt-3 space-y-2">
                {[...uploads].reverse().map((u) => (
                  <li
                    key={u.id}
                    className="flex items-start justify-between gap-2 rounded-xl border border-line bg-well px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink">{u.filename}</p>
                      <div className="mt-1">
                        <UploadStatusBadge status={u.status} />
                      </div>
                    </div>
                    <button
                      type="button"
                      className="focus-ring shrink-0 text-xs font-medium text-accent hover:underline"
                      onClick={() => setPreviewUpload(u)}
                    >
                      Preview
                    </button>
                  </li>
                ))}
                {uploads.length === 0 && (
                  <p className="text-xs text-muted">No evidence uploaded yet.</p>
                )}
              </ul>
            </div>
          </>
        )}

        {tab === "coverage" && (
          <>
            {coverage ? (
              <CoverageMeter widget={coverage} title={`${phaseLabel(coverage.phase)} checklist`} />
            ) : (
              <p className="text-xs text-muted">The checklist updates as the interview progresses.</p>
            )}
          </>
        )}

        {tab === "audit" && <AuditTrail events={auditEvents} detailFor={auditDetail} />}

        {tab === "knowledge" && (
          <CardList cards={cards} busy={busy} onEdit={editCard} onRetire={retireCard} />
        )}
      </div>
    </div>
  ) : null;

  return (
    <AppShell
      account={account}
      projects={projects}
      selectedProjectId={id}
      onProjectsRefresh={() => void refreshShell()}
      rightTab={tab}
      onRightTabChange={onWorkspaceTab}
      rightTabLabels={tabLabels}
      rightPanel={rightPanel}
    >
      {loading && <p className="px-6 py-8 text-sm text-muted">Loading project...</p>}

      {error && !loading && !missing && (
        <p className="px-6 py-8 text-sm text-amber-700">
          {error}{" "}
          <button
            type="button"
            className="text-accent underline"
            onClick={() => {
              setLoading(true);
              loadWorkspace();
            }}
          >
            Retry
          </button>
        </p>
      )}

      {missing && !loading && (
        <p className="px-6 py-8 text-sm text-muted">
          Project not found.{" "}
          <Link href="/" className="text-accent">
            Back home
          </Link>
        </p>
      )}

      {project && !loading && (
        <section className="flex h-full min-h-0 flex-col">
          <WorkspaceHeader
            projectId={project.id}
            name={project.name}
            phase={project.phase}
            chatTab={chatTab}
            mode={mode}
            busy={busy}
            onRedraft={() => void redraftRequirements()}
            onRenamed={(updated) => {
              setProject(updated);
              setProjects((prev) =>
                prev.map((p) => (p.id === updated.id ? { ...p, name: updated.name } : p)),
              );
            }}
            tabLabels={tabLabels}
          />

          <div className="flex shrink-0 gap-1 border-b border-line/60 px-4">
            {(["planning", "requirements"] as const).map((key) => (
              <button
                key={key}
                type="button"
                className={`focus-ring px-3 py-2 text-xs font-medium capitalize ${
                  chatTab === key
                    ? "border-b-2 border-accent text-ink"
                    : "text-muted hover:text-ink"
                }`}
                onClick={() => void switchChatTab(key)}
              >
                {key === "planning" ? "Planning" : "Requirements"}
              </button>
            ))}
            {!tabWritable && chatTab === "planning" && project && project.phase !== "planning" && (
              <button
                type="button"
                disabled={busy}
                className="focus-ring ml-auto self-center rounded-lg border border-line px-2.5 py-1 text-[11px] font-medium text-muted hover:bg-well disabled:opacity-50"
                onClick={() => void goToPlanning(null)}
              >
                Reopen Planning
              </button>
            )}
            {!tabWritable && chatTab === "requirements" && (
              <span className="ml-auto self-center text-[11px] text-muted">
                Locked until the Charter is accepted
              </span>
            )}
          </div>

          {chatTab === "requirements" && chatState?.requirements_stale_since && (
            <div className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
              Planning was revised after these requirements were drafted — use{" "}
              <button
                type="button"
                disabled={busy}
                className="underline hover:no-underline disabled:opacity-50"
                onClick={() => void redraftRequirements()}
              >
                Redraft requirements
              </button>{" "}
              to refresh them.
            </div>
          )}

          {showCenteredEmpty ? (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4">
              <Composer
                draft={draft}
                setDraft={setDraft}
                canAnswer={canAnswer}
                busy={busy}
                recording={recording}
                transcribing={transcribing}
                recordError={recordError}
                attachedFiles={attachedFiles}
                pendingUploads={pendingUploads}
                failedUploads={failedUploads}
                fileInputRef={fileInputRef}
                textareaRef={textareaRef}
                onSend={() => void send({ content: draft.trim() })}
                onAttach={() => fileInputRef.current?.click()}
                onFiles={queueFiles}
                onRemoveFile={(index) =>
                  setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
                }
                onDrop={handleDrop}
                onPaste={handlePaste}
                onStartRecording={() => void startRecording()}
                onStopRecording={stopRecording}
                error={error}
              />
            </div>
          ) : (
            <>
              <div
                ref={chatScroll}
                className="sidebar-scroll min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-2"
                onScroll={(e) => {
                  const el = e.currentTarget;
                  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
                  pinnedToBottom.current = atBottom;
                  setShowScrollDown(!atBottom);
                }}
              >
                <div className="mx-auto min-w-0 max-w-[48rem] space-y-4 pb-4">
                  {ingestNotice && (
                    <IngestCompleteNotice
                      message={ingestNotice}
                      onDismiss={() => setIngestNotice("")}
                    />
                  )}
                  {(reading || failedUploads.length > 0 || flaggedUploads.length > 0) && tabWritable && (
                    <IngestProgressBanner uploads={uploads} />
                  )}
                  {!tabWritable && messages.length === 0 && (
                    <p className="text-sm text-muted">
                      {chatTab === "requirements"
                        ? "The Requirements interview starts after you accept the Project Charter."
                        : "This Planning transcript is read-only after Charter accept."}
                    </p>
                  )}
                  {messages.map((message, idx) => (
                    <ChatTurn
                      key={message.id}
                      message={message}
                      typewriter={message.id === typewriterId}
                      isLastQuestion={
                        idx === lastQuestionIdx && mode === "interview" && !hasOpenConflicts
                      }
                      isActiveGate={
                        mode === "gate" &&
                        (idx === activeGateWidgetIdx || (gateGenFailed && idx === lastPickerIdx))
                      }
                      busy={busy}
                      uploads={uploads}
                      onSubmitQuestion={handleQuestionSubmit}
                      onSkipQuestion={handleSkipQuestion}
                      onAcceptGate={() => void acceptGate()}
                      onReviseGate={(area, content) => void reviseGate(area, content)}
                      onSelectPacks={(packIds) => void selectPacks(packIds)}
                      onKeepUpload={(uploadId) => void keepFlaggedUpload(uploadId)}
                      onDiscardUpload={(uploadId) => void discardFlaggedUpload(uploadId)}
                      isLastRedirectSuggestion={idx === lastRedirectSuggestionIdx}
                      onGoToPlanning={(area) => void goToPlanning(area)}
                      onKeepHere={(excerpt) => void keepHere(excerpt)}
                    />
                  ))}
                  {streaming && (
                    <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted animate-pulse">
                      CrewLane is thinking…
                    </p>
                  )}
                </div>
              </div>

              <div className="relative shrink-0 px-4 py-3">
                {showScrollDown && (
                  <button
                    type="button"
                    className="focus-ring absolute left-1/2 top-0 z-10 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-well text-ink shadow-md"
                    title="Jump to latest"
                    onClick={() => {
                      pinnedToBottom.current = true;
                      setShowScrollDown(false);
                      const el = chatScroll.current;
                      if (el) el.scrollTop = el.scrollHeight;
                    }}
                  >
                    <ScrollDownIcon />
                  </button>
                )}
                {activeConflict && (
                  <div className="mx-auto mb-3 w-full max-w-[48rem]">
                    <ConflictCard
                      widget={conflictToWidget(activeConflict)}
                      hint="Resolve all conflicts to continue the interview. Ask in chat for a recommendation."
                      recommendation={
                        activeConflict &&
                        (conflictAdvice?.pick === "a" || conflictAdvice?.pick === "b")
                          ? {
                              pick: conflictAdvice.pick as "a" | "b",
                              why: conflictAdvice.why,
                            }
                          : undefined
                      }
                      busy={busy}
                      isActive
                      onResolve={(conflictId, winnerId) =>
                        void resolveConflict(conflictId, winnerId)
                      }
                    />
                  </div>
                )}
                <Composer
                  draft={draft}
                  setDraft={setDraft}
                  canAnswer={canAnswer}
                  busy={busy}
                  recording={recording}
                  transcribing={transcribing}
                  recordError={recordError}
                  attachedFiles={attachedFiles}
                  pendingUploads={pendingUploads}
                  failedUploads={failedUploads}
                  fileInputRef={fileInputRef}
                  textareaRef={textareaRef}
                  onSend={() => void send({ content: draft.trim() })}
                  onAttach={() => fileInputRef.current?.click()}
                  onFiles={queueFiles}
                  onRemoveFile={(index) =>
                    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
                  }
                  onDrop={handleDrop}
                  onPaste={handlePaste}
                  onStartRecording={() => void startRecording()}
                  onStopRecording={stopRecording}
                  error={error}
                />
              </div>
            </>
          )}
        </section>
      )}

      {previewUpload && (
        <EvidencePreviewModal
          projectId={id}
          upload={previewUpload}
          onClose={() => setPreviewUpload(null)}
        />
      )}
    </AppShell>
  );
}

function WorkspaceHeader({
  projectId,
  name,
  phase,
  chatTab,
  mode,
  busy,
  onRedraft,
  onRenamed,
  tabLabels,
}: {
  projectId: string;
  name: string;
  phase: string;
  chatTab: ChatPhaseTab;
  mode: string;
  busy: boolean;
  onRedraft: () => void;
  onRenamed: (project: Project) => void;
  tabLabels: Record<WorkspaceTab, string>;
}) {
  const { leftCollapsed, rightOpen, toggleLeft } = useShellChrome();
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(name);
  const [renaming, setRenaming] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const startEdit = () => {
    setDraftName(name);
    setEditing(true);
  };

  const commitRename = async () => {
    const next = draftName.trim();
    if (!next || next === name) {
      setEditing(false);
      return;
    }
    setRenaming(true);
    try {
      const updated = await api.renameProject(projectId, next);
      onRenamed(updated);
      setEditing(false);
    } catch {
      setEditing(false);
    } finally {
      setRenaming(false);
    }
  };

  return (
    <div className="flex h-12 w-full shrink-0 items-center gap-2 border-b border-line/60 px-3">
      {leftCollapsed && (
        <button
          type="button"
          className={`${ICON_BTN} hidden lg:inline-flex`}
          title="Open projects"
          onClick={toggleLeft}
        >
          <SidebarToggleIcon flipped />
        </button>
      )}
      {editing ? (
        <input
          ref={inputRef}
          className="focus-ring min-w-0 max-w-[16rem] flex-1 truncate rounded-md border border-line bg-well px-2 py-1 text-sm font-semibold tracking-tight text-ink"
          value={draftName}
          disabled={renaming}
          maxLength={120}
          aria-label="Project name"
          onChange={(e) => setDraftName(e.target.value)}
          onBlur={() => void commitRename()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void commitRename();
            }
            if (e.key === "Escape") {
              setEditing(false);
            }
          }}
        />
      ) : (
        <button
          type="button"
          className="focus-ring min-w-0 truncate rounded-md px-1 py-0.5 text-left text-sm font-semibold tracking-tight text-ink hover:bg-well"
          title="Rename project"
          onClick={startEdit}
        >
          {name}
        </button>
      )}
      <span className="text-muted">·</span>
      <span className="min-w-0 truncate text-sm text-muted">
        {phaseLabel(chatTab)}
        {mode === "gate" ? " · Gate" : phase === "done" && chatTab === "requirements" ? " · Free chat" : ""}
      </span>
      {phase === "done" && (
        <button
          type="button"
          className="focus-ring ml-auto shrink-0 rounded-lg border border-line bg-well px-3 py-1.5 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-50"
          disabled={busy}
          onClick={onRedraft}
        >
          {busy ? "Starting…" : "Redraft requirements"}
        </button>
      )}
      {!rightOpen && (
        <div className={`hidden shrink-0 lg:block ${phase === "done" ? "" : "ml-auto"}`}>
          <RightPanelMenu labels={tabLabels} />
        </div>
      )}
    </div>
  );
}

function Composer({
  draft,
  setDraft,
  canAnswer,
  busy,
  recording,
  transcribing,
  recordError,
  attachedFiles,
  pendingUploads,
  failedUploads,
  fileInputRef,
  textareaRef,
  onSend,
  onAttach,
  onFiles,
  onRemoveFile,
  onDrop,
  onPaste,
  onStartRecording,
  onStopRecording,
  error,
}: {
  draft: string;
  setDraft: (v: string) => void;
  canAnswer: boolean;
  busy: boolean;
  recording: boolean;
  transcribing: boolean;
  recordError: string;
  attachedFiles: File[];
  pendingUploads: Upload[];
  failedUploads: Upload[];
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  onSend: () => void;
  onAttach: () => void;
  onFiles: (files: FileList | File[]) => void;
  onRemoveFile: (index: number) => void;
  onDrop: (e: React.DragEvent) => void;
  onPaste: (e: React.ClipboardEvent) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  error: string;
}) {
  useAutoResizeTextarea(textareaRef, draft);
  const canSend = canAnswer && (draft.trim().length > 0 || attachedFiles.length > 0);

  return (
    <form
      className="mx-auto w-full max-w-[48rem]"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSend) return;
        onSend();
      }}
      onDrop={onDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      {(attachedFiles.length > 0 ||
        recording ||
        transcribing ||
        pendingUploads.length > 0 ||
        failedUploads.length > 0) && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {attachedFiles.map((file, index) => (
            <span
              key={`${file.name}-${index}`}
              className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-0.5 text-xs text-accent"
            >
              {file.name}
              <button
                type="button"
                className="ml-1 text-accent/60 hover:text-accent"
                onClick={() => onRemoveFile(index)}
              >
                ×
              </button>
            </span>
          ))}
          {recording && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs text-red-700 animate-pulse">
              Recording…
            </span>
          )}
          {transcribing && (
            <span className="inline-flex items-center gap-1 rounded-full bg-well px-2.5 py-0.5 text-xs text-muted">
              Transcribing…
            </span>
          )}
          {pendingUploads.map((u) => {
            const pill = composerIngestPill(u);
            return (
              <span
                key={u.id}
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs ${pill.tone}`}
              >
                {u.filename} · {pill.label}
              </span>
            );
          })}
          {failedUploads.map((u) => (
            <span
              key={u.id}
              className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-0.5 text-xs text-red-800"
              title={u.last_error ?? undefined}
            >
              {u.filename} · Failed
            </span>
          ))}
        </div>
      )}
      {recordError && <p className="mb-2 text-xs text-amber-700">{recordError}</p>}

      <div className="flex items-center gap-1.5 rounded-full border border-line bg-well px-2 py-1.5 shadow-sm">
        <button
          type="button"
          className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted hover:text-accent disabled:opacity-50"
          disabled={busy}
          onClick={onAttach}
          title="Attach file"
        >
          <PaperclipIcon />
        </button>
        {recording ? (
          <button
            type="button"
            className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-600 text-white"
            onClick={onStopRecording}
            title="Stop recording"
          >
            <StopIcon />
          </button>
        ) : (
          <button
            type="button"
            className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted hover:text-accent disabled:opacity-50"
            disabled={busy || transcribing}
            onClick={onStartRecording}
            title="Record voice"
          >
            <MicIcon />
          </button>
        )}

        <textarea
          ref={textareaRef}
          className="max-h-[120px] min-h-[36px] flex-1 resize-none border-0 bg-transparent px-1 py-2 text-sm leading-5 text-ink outline-none ring-0 focus:outline-none focus:ring-0"
          rows={1}
          value={draft}
          disabled={!canAnswer}
          onChange={(e) => setDraft(e.target.value)}
          onPaste={onPaste}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
        />

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept={FILE_ACCEPT}
          multiple
          onChange={(e) => {
            if (e.target.files?.length) onFiles(e.target.files);
            if (fileInputRef.current) fileInputRef.current.value = "";
          }}
        />

        <button
          type="submit"
          className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink disabled:opacity-40"
          disabled={!canSend}
          title={busy ? "Sending…" : "Send"}
        >
          <SendIcon />
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-amber-700">{error}</p>}
    </form>
  );
}

function PaperclipIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M19 10v2a7 7 0 01-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function ScrollDownIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d="M12 5v14M6 13l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
