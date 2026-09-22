"use client";

import type { Upload } from "@/lib/api";
import {
  ingestSummary,
  isUploadPending,
  pendingUploads,
  uploadStatus,
  uploadStatusLabel,
  uploadStatusTone,
} from "@/lib/uploads";

export function UploadStatusBadge({ status }: { status: string }) {
  const normalized = uploadStatus(status);
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${uploadStatusTone(normalized)}`}
    >
      {normalized === "processing" && (
        <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {uploadStatusLabel(normalized)}
    </span>
  );
}

export function UploadStatusRow({ upload }: { upload: Upload }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-2 border-b border-line py-2 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-ink">{upload.filename}</p>
        {upload.speaker_name && (
          <p className="mt-0.5 text-xs text-muted">Speaker: {upload.speaker_name}</p>
        )}
        {upload.last_error && (
          <p className="mt-1 break-words text-xs text-red-700">{upload.last_error}</p>
        )}
      </div>
      <UploadStatusBadge status={upload.status} />
    </li>
  );
}

export function UploadStatusList({
  uploads,
  emptyLabel = "No evidence uploaded yet.",
}: {
  uploads: Upload[];
  emptyLabel?: string;
}) {
  if (uploads.length === 0) {
    return <p className="text-xs text-muted">{emptyLabel}</p>;
  }
  return (
    <ul className="divide-y divide-line">
      {[...uploads].reverse().map((upload) => (
        <UploadStatusRow key={upload.id} upload={upload} />
      ))}
    </ul>
  );
}

export function IngestProgressBanner({ uploads }: { uploads: Upload[] }) {
  const pending = pendingUploads(uploads);
  const failed = uploads.filter((u) => u.status === "failed");
  const flagged = uploads.filter((u) => u.status === "flagged");
  if (pending.length === 0 && failed.length === 0 && flagged.length === 0) return null;

  return (
    <div className="rounded-xl border border-line bg-well/90 p-4 shadow-sm">
      {pending.length > 0 && (
        <>
          <p className="animate-pulse text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
            Reading your material…
          </p>
          <ul className="mt-3 space-y-2">
            {uploads.map((upload) => (
              <li key={upload.id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="truncate text-muted">{upload.filename}</span>
                <UploadStatusBadge status={upload.status} />
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">
            The interview starts once everything has been read, so the first question is
            about what&apos;s actually missing.
          </p>
        </>
      )}
      {failed.length > 0 && (
        <div className={pending.length > 0 ? "mt-4 border-t border-line pt-3" : ""}>
          <p className="text-xs font-medium text-red-800">
            {failed.length} file{failed.length === 1 ? "" : "s"} could not be read
          </p>
          <ul className="mt-2 space-y-1 text-xs text-red-700">
            {failed.map((upload) => (
              <li key={upload.id}>
                {upload.filename}
                {upload.last_error ? ` — ${upload.last_error}` : ""}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">
            You can keep chatting — CrewLane will use whatever was read successfully.
          </p>
        </div>
      )}
      {flagged.length > 0 && (
        <div className={pending.length > 0 || failed.length > 0 ? "mt-4 border-t border-line pt-3" : ""}>
          <p className="text-xs font-medium text-amber-800">
            {flagged.length} file{flagged.length === 1 ? "" : "s"} need review — looks unrelated
            to this project
          </p>
          <ul className="mt-2 space-y-1 text-xs text-amber-700">
            {flagged.map((upload) => (
              <li key={upload.id}>{upload.filename}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">
            Decide in chat below — Keep anyway or Discard.
          </p>
        </div>
      )}
    </div>
  );
}

export function IngestCompleteNotice({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
      <p>{message}</p>
      <button
        type="button"
        className="shrink-0 text-emerald-700 hover:text-emerald-900"
        onClick={onDismiss}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

export function uploadTabLabel(count: number, uploads: Upload[]): string {
  const pending = pendingUploads(uploads).length;
  if (pending === 0) return `Evidence (${count})`;
  return `Evidence (${count}) · ${pending} reading`;
}

export function composerIngestPill(upload: Upload) {
  const tone =
    upload.status === "failed"
      ? "bg-red-50 text-red-800"
      : upload.status === "flagged"
        ? "bg-amber-50 text-amber-800"
        : upload.status === "queued"
          ? "bg-surface text-muted"
          : "bg-accent/10 text-accent";
  const label =
    upload.status === "failed"
      ? "Failed"
      : upload.status === "flagged"
        ? "Needs review"
        : upload.status === "queued"
          ? "Queued"
          : "Processing";
  return { tone, label };
}

export function summarizeIngestBatch(uploads: Upload[]): string | null {
  return ingestSummary(uploads.filter((u) => !isUploadPending(u.status)));
}
