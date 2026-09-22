"use client";

import { useRef, useState } from "react";
import type { Upload } from "@/lib/api";
import { pendingUploads } from "@/lib/uploads";
import { UploadStatusBadge } from "@/components/widgets/upload-status";

type Props = {
  uploads: Upload[];
  busy: boolean;
  onUpload: (file: File, speakerName?: string) => Promise<void>;
  onLink: (url: string) => Promise<void>;
};

export function UploadPanel({ uploads, busy, onUpload, onLink }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [speaker, setSpeaker] = useState("");
  const [url, setUrl] = useState("");
  const [recording, setRecording] = useState(false);
  const [recordError, setRecordError] = useState("");

  const pending = pendingUploads(uploads);

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
        void onUpload(file, speaker.trim() || undefined);
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setRecordError("Microphone unavailable - check browser permissions.");
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  };

  const submitLink = async () => {
    if (!url.trim()) return;
    await onLink(url.trim());
    setUrl("");
  };

  return (
    <div className="well-panel p-4">
      <h2 className="text-sm font-semibold text-ink">Evidence intake</h2>
      <p className="mt-1 text-xs text-muted">
        Upload documents, transcripts, images, or audio — or record a voice note here to ingest
        as evidence. Facts appear in Knowledge when processing finishes.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-muted">
          Speaker (optional)
          <input
            className="focus-ring rounded-lg border border-line bg-well px-2.5 py-1.5 text-sm text-ink"
            value={speaker}
            disabled={busy || recording}
            placeholder="Who is speaking / who wrote it?"
            onChange={(e) => setSpeaker(e.target.value)}
          />
        </label>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".txt,.md,.pdf,.docx,.xlsx,.pptx,.csv,.vtt,.srt,.html,.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.m4a,.mp4,.webm,.ogg,.flac"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            void onUpload(file, speaker.trim() || undefined).finally(() => {
              if (inputRef.current) inputRef.current.value = "";
            });
          }}
        />
        <button
          type="button"
          className="focus-ring rounded-lg border border-line bg-glass px-3 py-1.5 text-sm text-ink disabled:opacity-50"
          disabled={busy || recording}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? "Uploading…" : "Upload file"}
        </button>
        {recording ? (
          <button
            type="button"
            className="focus-ring rounded-lg bg-amber-700 px-3 py-1.5 text-sm font-medium text-white"
            onClick={stopRecording}
          >
            ■ Stop &amp; ingest
          </button>
        ) : (
          <button
            type="button"
            className="focus-ring rounded-lg border border-line bg-glass px-3 py-1.5 text-sm text-ink disabled:opacity-50"
            disabled={busy}
            onClick={() => void startRecording()}
          >
            ● Record voice
          </button>
        )}
      </div>
      {recording && (
        <p className="mt-2 text-xs text-amber-700">Recording… speak your idea, then stop.</p>
      )}
      {recordError && <p className="mt-2 text-xs text-amber-700">{recordError}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          className="focus-ring min-w-[14rem] flex-1 rounded-lg border border-line bg-well px-2.5 py-1.5 text-sm"
          placeholder="Or paste a link (spec page, wiki, doc)…"
          value={url}
          disabled={busy}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button
          type="button"
          className="focus-ring rounded-lg border border-line bg-glass px-3 py-1.5 text-sm text-ink disabled:opacity-50"
          disabled={busy || !url.trim()}
          onClick={() => void submitLink()}
        >
          Fetch page
        </button>
      </div>
      {pending.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <p className="text-xs font-medium text-muted">
            Processing {pending.length} upload{pending.length === 1 ? "" : "s"}…
          </p>
          <ul className="mt-2 space-y-2">
            {pending.map((upload) => (
              <li key={upload.id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="truncate text-muted">{upload.filename}</span>
                <UploadStatusBadge status={upload.status} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
