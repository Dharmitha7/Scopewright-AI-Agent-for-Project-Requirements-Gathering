import type { Upload } from "@/lib/api";

export type UploadStatus = "queued" | "processing" | "done" | "failed" | "flagged" | "discarded";

export function uploadStatus(value: string): UploadStatus {
  if (
    value === "queued" ||
    value === "processing" ||
    value === "done" ||
    value === "failed" ||
    value === "flagged" ||
    value === "discarded"
  ) {
    return value;
  }
  return "queued";
}

export function uploadStatusLabel(status: UploadStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "processing":
      return "Processing";
    case "done":
      return "Done";
    case "failed":
      return "Failed";
    case "flagged":
      return "Needs review";
    case "discarded":
      return "Discarded";
  }
}

export function uploadStatusTone(status: UploadStatus): string {
  switch (status) {
    case "queued":
      return "bg-surface text-muted border-line";
    case "processing":
      return "bg-accent/10 text-accent border-accent/20";
    case "done":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "failed":
      return "bg-red-50 text-red-800 border-red-200";
    case "flagged":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "discarded":
      return "bg-surface text-muted border-line";
  }
}

export function isUploadPending(status: string): boolean {
  return status === "queued" || status === "processing";
}

export function pendingUploads(uploads: Upload[]): Upload[] {
  return uploads.filter((u) => isUploadPending(u.status));
}

export function failedUploads(uploads: Upload[]): Upload[] {
  return uploads.filter((u) => u.status === "failed");
}

export function flaggedUploads(uploads: Upload[]): Upload[] {
  return uploads.filter((u) => u.status === "flagged");
}

export function ingestSummary(uploads: Upload[]): string | null {
  const done = uploads.filter((u) => u.status === "done");
  const failed = failedUploads(uploads);
  const flagged = flaggedUploads(uploads);
  if (done.length === 0 && failed.length === 0 && flagged.length === 0) return null;
  const parts: string[] = [];
  if (done.length > 0) {
    parts.push(`Read ${done.length} file${done.length === 1 ? "" : "s"}`);
  }
  if (flagged.length > 0) {
    parts.push(`${flagged.length} needs review`);
  }
  if (failed.length > 0) {
    parts.push(`${failed.length} failed`);
  }
  return parts.join(" · ");
}
