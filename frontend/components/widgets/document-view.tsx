"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { BrandedDocumentPreview } from "@/components/branded-document";
import { Markdown } from "@/components/markdown";
import { packLabel, packShortLabel } from "@/lib/deliverables";
import { snapshotExportUrl, type Snapshot } from "@/lib/api";

const FORMATS = ["md", "docx", "pdf"] as const;

function documentTitle(snapshot: Snapshot): string {
  const raw = snapshot.document.trim();
  if (/charter/i.test(raw)) return "Project Charter";
  if (/requirement/i.test(raw)) return "Requirements Deliverables";
  return raw;
}

export function DocumentView({
  projectId,
  projectName,
  snapshot,
}: {
  projectId: string;
  projectName: string;
  snapshot: Snapshot;
}) {
  const [open, setOpen] = useState(false);
  const packEntries = snapshot.narratives?.packs
    ? Object.entries(snapshot.narratives.packs)
    : [];
  const tags =
    packEntries.length > 0
      ? packEntries.slice(0, 4).map(([key]) => packShortLabel(key))
      : snapshot.phase === "planning"
        ? ["Objectives", "Scope", "Stakeholders"]
        : ["Stories", "Traceability", "Quality"];

  return (
    <>
      <article className="well-panel flex flex-col p-4 shadow-[0_4px_20px_rgba(24,36,66,0.06)]">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
            <DocIcon />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold tracking-tight text-ink" title={documentTitle(snapshot)}>
              {documentTitle(snapshot)}
            </h3>
            <p className="mt-0.5 text-xs text-muted">
              {new Date(snapshot.created_at).toLocaleString(undefined, {
                month: "numeric",
                day: "numeric",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
            </p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full border border-line bg-well px-2.5 py-0.5 text-[11px] text-muted"
            >
              <TagIcon />
              {tag}
            </span>
          ))}
          {packEntries.length > 4 && (
            <span className="rounded-full border border-line px-2.5 py-0.5 text-[11px] text-muted">
              +{packEntries.length - 4}
            </span>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          <button
            type="button"
            className="focus-ring rounded-lg px-1 py-1.5 text-sm font-medium text-accent hover:underline"
            onClick={() => setOpen(true)}
          >
            Preview
          </button>
          <DownloadMenu projectId={projectId} snapshotId={snapshot.id} />
        </div>
      </article>

      {open && (
        <SnapshotReaderModal
          projectId={projectId}
          projectName={projectName}
          snapshot={snapshot}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

function SnapshotReaderModal({
  projectId,
  projectName,
  snapshot,
  onClose,
}: {
  projectId: string;
  projectName: string;
  snapshot: Snapshot;
  onClose: () => void;
}) {
  const packEntries = snapshot.narratives?.packs
    ? Object.entries(snapshot.narratives.packs)
    : [];
  const hasNarrative = Boolean(snapshot.narrative) || packEntries.length > 0;
  const [tab, setTab] = useState<"narrative" | "audit">(hasNarrative ? "narrative" : "audit");
  const [packKey, setPackKey] = useState<string | null>(
    snapshot.narratives?.mode === "separate" && packEntries[0] ? packEntries[0][0] : null,
  );

  const narrativeBody =
    packKey && snapshot.narratives?.packs?.[packKey]
      ? snapshot.narratives.packs[packKey]
      : snapshot.narrative || snapshot.narratives?.combined || "";
  const body = tab === "narrative" && hasNarrative ? narrativeBody : snapshot.body;
  const modalTitle =
    tab === "narrative" && packKey ? packLabel(packKey) : documentTitle(snapshot);

  const previewMeta = {
    title: modalTitle,
    documentType:
      snapshot.phase === "planning"
        ? "PROJECT CHARTER"
        : packKey
          ? packLabel(packKey).toUpperCase()
          : "REQUIREMENTS DELIVERABLES",
    documentNumber:
      snapshot.phase === "planning"
        ? `CHR-${String(snapshot.id).slice(0, 3).toUpperCase()}`
        : `REQ-${(packKey ?? "DOC").slice(0, 3).toUpperCase()}`,
    version: "1.0",
    effectiveDate: new Date(snapshot.created_at).toLocaleDateString(),
    projectName,
  };

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
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-line bg-well shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-ink" title={modalTitle}>
              {modalTitle}
            </p>
            <p className="mt-0.5 font-mono text-[10px] text-muted">
              snapshot {snapshot.id.slice(0, 8)} · {new Date(snapshot.created_at).toISOString()}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {FORMATS.map((format) => (
              <a
                key={format}
                className="focus-ring inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-[10px] font-medium uppercase text-muted hover:text-ink"
                href={snapshotExportUrl(projectId, snapshot.id, format, packKey ?? undefined)}
                title={`Download ${format.toUpperCase()}`}
              >
                <DownloadIcon />
                {format}
              </a>
            ))}
            <button
              type="button"
              className="focus-ring ml-1 rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink"
              onClick={onClose}
              title="Close (Esc)"
              aria-label="Close"
            >
              <CloseIcon />
            </button>
          </div>
        </div>

        <div className="shrink-0 space-y-2 border-b border-line px-5 py-3">
          {packEntries.length > 1 && tab === "narrative" && (
            <div className="flex flex-wrap gap-1.5">
              <PackChip active={!packKey} title="All selected packs" onClick={() => setPackKey(null)}>
                All packs
              </PackChip>
              {packEntries.map(([key]) => (
                <PackChip
                  key={key}
                  active={packKey === key}
                  title={packLabel(key)}
                  onClick={() => setPackKey(key)}
                >
                  {packShortLabel(key)}
                </PackChip>
              ))}
            </div>
          )}
          {hasNarrative && (
            <div className="flex gap-1">
              <TabButton active={tab === "narrative"} onClick={() => setTab("narrative")}>
                Document
              </TabButton>
              <TabButton active={tab === "audit"} onClick={() => setTab("audit")}>
                Audit (card-exact)
              </TabButton>
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 text-ink">
          {tab === "narrative" && hasNarrative ? (
            <BrandedDocumentPreview meta={previewMeta} body={body} />
          ) : (
            <Markdown text={body} />
          )}
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}

function DownloadMenu({ projectId, snapshotId }: { projectId: string; snapshotId: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        className="focus-ring rounded-lg bg-accent px-3.5 py-1.5 text-sm font-medium text-accent-ink"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Download
      </button>
      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-10 cursor-default"
            aria-label="Close download menu"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 bottom-full z-20 mb-1.5 min-w-[7rem] overflow-hidden rounded-xl border border-line bg-well py-1 shadow-lg">
            {FORMATS.map((format) => (
              <a
                key={format}
                className="block px-3 py-1.5 text-xs font-medium uppercase text-ink hover:bg-canvas"
                href={snapshotExportUrl(projectId, snapshotId, format)}
                onClick={() => setOpen(false)}
              >
                {format}
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function DocIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function TagIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z" />
      <line x1="7" y1="7" x2="7.01" y2="7" />
    </svg>
  );
}

function PackChip({
  active,
  title,
  onClick,
  children,
}: {
  active: boolean;
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      className={`focus-ring rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "bg-accent text-accent-ink"
          : "border border-line bg-well text-ink hover:border-accent/40"
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={`focus-ring rounded-lg px-2.5 py-1 text-xs font-medium ${
        active ? "bg-accent text-accent-ink" : "border border-line text-muted hover:bg-canvas"
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
