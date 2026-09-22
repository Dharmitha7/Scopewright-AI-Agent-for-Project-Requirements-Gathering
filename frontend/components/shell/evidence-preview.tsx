"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Markdown } from "@/components/markdown";
import { uploadContentUrl, type Upload } from "@/lib/api";

type Props = {
  projectId: string;
  upload: Upload;
  onClose: () => void;
};

function isImage(ct: string, name: string) {
  return ct.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(name);
}

function isPdf(ct: string, name: string) {
  return ct.includes("pdf") || /\.pdf$/i.test(name);
}

function isAudio(ct: string, name: string) {
  return ct.startsWith("audio/") || /\.(wav|mp3|m4a|ogg|flac|webm)$/i.test(name);
}

function isTextLike(ct: string, name: string) {
  return (
    ct.startsWith("text/") ||
    ct.includes("json") ||
    /\.(txt|md|markdown|csv|html?|vtt|srt|json)$/i.test(name)
  );
}

export function EvidencePreviewModal({ projectId, upload, onClose }: Props) {
  const url = uploadContentUrl(projectId, upload.id);
  const textLike = isTextLike(upload.content_type, upload.filename);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(textLike);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (!textLike) return;
    let cancelled = false;
    fetch(url, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.text();
      })
      .then((body) => {
        if (!cancelled) setText(body);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "could not load file");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [url, textLike]);

  const officeLike = /\.(docx?|xlsx?|pptx?)$/i.test(upload.filename);

  const modal = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-line bg-well shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink" title={upload.filename}>
              {upload.filename}
            </p>
            <p className="mt-0.5 text-[10px] text-muted">
              {upload.content_type} · {upload.status}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <a
              className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:text-ink"
              href={url}
              download={upload.filename}
            >
              <DownloadGlyph />
              Download
            </a>
            <button
              type="button"
              className="focus-ring rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink"
              onClick={onClose}
              title="Close (Esc)"
              aria-label="Close"
            >
              <CloseGlyph />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-5">
          {error && <p className="text-sm text-amber-700">{error}</p>}
          {loading && <p className="text-sm text-muted">Loading…</p>}

          {isPdf(upload.content_type, upload.filename) && (
            <iframe title={upload.filename} src={url} className="h-[70vh] w-full rounded-lg border border-line" />
          )}

          {isImage(upload.content_type, upload.filename) && (
            // eslint-disable-next-line @next/next/no-img-element -- cookie-auth preview URL
            <img src={url} alt={upload.filename} className="mx-auto max-h-[70vh] max-w-full rounded-lg" />
          )}

          {isAudio(upload.content_type, upload.filename) && (
            <audio controls className="w-full" src={url}>
              <track kind="captions" />
            </audio>
          )}

          {textLike && text !== null && (
            /\.(md|markdown)$/i.test(upload.filename) ? (
              <Markdown text={text} />
            ) : (
              <pre className="whitespace-pre-wrap break-words font-mono text-xs text-ink">{text}</pre>
            )
          )}

          {officeLike && (
            <div className="space-y-3 text-sm text-muted">
              <p>Office files open best via download. Preview of the original binary isn’t rendered in-browser.</p>
              <a
                className="focus-ring inline-flex rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-ink"
                href={url}
                download={upload.filename}
              >
                Download {upload.filename}
              </a>
            </div>
          )}

          {!isPdf(upload.content_type, upload.filename) &&
            !isImage(upload.content_type, upload.filename) &&
            !isAudio(upload.content_type, upload.filename) &&
            !textLike &&
            !officeLike && (
              <div className="space-y-3 text-sm text-muted">
                <p>No in-browser preview for this type.</p>
                <a
                  className="focus-ring inline-flex rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-ink"
                  href={url}
                  download={upload.filename}
                >
                  Download {upload.filename}
                </a>
              </div>
            )}
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}

function DownloadGlyph() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function CloseGlyph() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
