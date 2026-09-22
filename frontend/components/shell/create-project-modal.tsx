"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";

const FILE_ACCEPT =
  ".txt,.md,.pdf,.docx,.xlsx,.pptx,.csv,.vtt,.srt,.html,.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.m4a,.mp4,.webm,.ogg,.flac";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (id: string) => void;
};

export function CreateProjectModal({ open, onClose, onCreated }: Props) {
  const [projectName, setProjectName] = useState("");
  const [brief, setBrief] = useState("");
  const [link, setLink] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((prev) => [...prev, ...Array.from(incoming)]);
  };

  const create = async () => {
    if (!brief.trim()) return;
    setBusy(true);
    setError("");
    try {
      setStatus("Reading your brief…");
      const project = await api.createProject(brief.trim(), projectName.trim() || undefined);
      const jobs: Promise<unknown>[] = files.map((f) => api.uploadFile(project.id, f));
      if (link.trim()) jobs.push(api.ingestLink(project.id, link.trim()));
      if (jobs.length > 0) {
        setStatus("Sending your material…");
        await Promise.all(jobs);
      }
      setProjectName("");
      setBrief("");
      setLink("");
      setFiles([]);
      setStatus("");
      setBusy(false);
      onCreated(project.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not create project");
      setBusy(false);
      setStatus("");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="glass-panel-strong w-full max-w-lg p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onDrop={(e) => {
          e.preventDefault();
          addFiles(e.dataTransfer.files);
        }}
        onDragOver={(e) => e.preventDefault()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
              New project
            </p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink">
              What are you building?
            </h2>
          </div>
          <button
            type="button"
            className="focus-ring rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:text-ink"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <p className="mt-2 text-sm text-muted">
          Describe it, or drop documents, recordings, photos, or links. CrewLane reads them
          before asking questions.
        </p>

        <input
          className="focus-ring mt-4 w-full rounded-xl border border-line bg-well px-3 py-2.5 text-sm"
          placeholder="Project name (optional)"
          value={projectName}
          maxLength={120}
          onChange={(e) => setProjectName(e.target.value)}
        />
        <textarea
          className="focus-ring mt-3 w-full resize-y rounded-xl border border-line bg-well px-3 py-2.5 text-sm"
          rows={5}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="Describe the project in your own words."
        />
        <input
          className="focus-ring mt-3 w-full rounded-xl border border-line bg-well px-3 py-2.5 text-sm"
          placeholder="Paste a link to ingest (optional)"
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />

        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          accept={FILE_ACCEPT}
          onChange={(e) => {
            addFiles(e.target.files);
            if (fileInputRef.current) fileInputRef.current.value = "";
          }}
        />
        {files.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {files.map((f, i) => (
              <span
                key={`${f.name}-${i}`}
                className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-0.5 text-xs text-accent"
              >
                {f.name}
                <button
                  type="button"
                  className="ml-1 text-accent/60 hover:text-accent"
                  onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="focus-ring rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-accent-ink disabled:opacity-50"
            disabled={busy || !brief.trim()}
            onClick={() => void create()}
          >
            {busy ? status || "Creating…" : "Start"}
          </button>
          <button
            type="button"
            className="focus-ring rounded-xl border border-line bg-well px-4 py-2.5 text-sm text-ink disabled:opacity-50"
            disabled={busy}
            onClick={() => fileInputRef.current?.click()}
          >
            Attach files
          </button>
        </div>
        {error && <p className="mt-2 text-xs text-amber-700">{error}</p>}
      </div>
    </div>
  );
}
