"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell, ICON_BTN, useShellChrome } from "@/components/shell/app-shell";
import { SidebarToggleIcon } from "@/components/shell/sidebar-toggle-icon";
import { api, type Account, type Project } from "@/lib/api";
import { useAutoResizeTextarea } from "@/lib/use-auto-resize-textarea";

const FILE_ACCEPT =
  ".txt,.md,.pdf,.docx,.xlsx,.pptx,.csv,.vtt,.srt,.html,.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.m4a,.mp4,.webm,.ogg,.flac";

export default function Home() {
  const [account, setAccount] = useState<Account | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const me = await api.me();
      setAccount(me);
      const list = await api.listProjects();
      setProjects(list);
    } catch {
      setAccount(null);
      setProjects(null);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- session bootstrap
    void load();
  }, [load]);

  const signIn = async () => {
    if (!name.trim() || !email.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.devSession({ display_name: name.trim(), email: email.trim() });
      window.dispatchEvent(new Event("crewlane-auth"));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "sign-in failed");
    } finally {
      setBusy(false);
    }
  };

  if (!account || projects === null) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {!account ? (
            <SignInWall
              name={name}
              email={email}
              setName={setName}
              setEmail={setEmail}
              onSubmit={signIn}
              busy={busy}
              error={error}
            />
          ) : (
            <p className="text-sm text-muted">Loading…</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <AppShell account={account} projects={projects} onProjectsRefresh={() => void load()}>
      <EmptyLanding firstName={account.display_name.split(/\s+/)[0] || account.display_name} />
    </AppShell>
  );
}

function EmptyLanding({ firstName }: { firstName: string }) {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useAutoResizeTextarea(textareaRef, draft);
  const canCreate = draft.trim().length > 0 || attachedFiles.length > 0;

  const queueFiles = (files: FileList | File[]) => {
    const next = Array.from(files);
    if (next.length === 0) return;
    setAttachedFiles((prev) => [...prev, ...next]);
  };

  const create = async () => {
    const brief = draft.trim();
    if ((!brief && attachedFiles.length === 0) || busy) return;
    setBusy(true);
    setError("");
    const filesToUpload = [...attachedFiles];
    setAttachedFiles([]);
    try {
      const project = await api.createProject(brief || "New project");
      for (const file of filesToUpload) {
        await api.uploadFile(project.id, file);
      }
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not create project");
      setBusy(false);
    }
  };

  const startRecording = async () => {
    setError("");
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
        queueFiles([new File([blob], `recording-${stamp}.webm`, { type: blob.type })]);
        setTranscribing(false);
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setError("Microphone unavailable — check browser permissions.");
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
    setTranscribing(true);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <HomeChrome />
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6">
      <div className="w-full max-w-[48rem]">
        <h1 className="text-center text-2xl font-semibold tracking-tight text-ink sm:text-[1.75rem]">
          Hi {firstName}, what are you building?
        </h1>
        <form
          className="mt-8"
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
        >
          {(attachedFiles.length > 0 || recording || transcribing) && (
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
                    onClick={() =>
                      setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
                    }
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
              {transcribing && attachedFiles.length === 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-well px-2.5 py-0.5 text-xs text-muted">
                  Saving recording…
                </span>
              )}
            </div>
          )}

          <div className="flex items-center gap-1.5 rounded-full border border-line bg-well px-2 py-1.5 shadow-sm">
            <button
              type="button"
              className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted hover:text-accent disabled:opacity-50"
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
              title="Attach file"
            >
              <PaperclipIcon />
            </button>
            {recording ? (
              <button
                type="button"
                className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-600 text-white"
                onClick={stopRecording}
                title="Stop recording"
              >
                <StopIcon />
              </button>
            ) : (
              <button
                type="button"
                className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted hover:text-accent disabled:opacity-50"
                disabled={busy}
                onClick={() => void startRecording()}
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
              disabled={busy}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (canCreate) void create();
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
                if (e.target.files?.length) queueFiles(e.target.files);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            />

            <button
              type="submit"
              className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink disabled:opacity-40"
              disabled={busy || !canCreate}
              title={busy ? "Creating…" : "Start"}
            >
              <SendIcon />
            </button>
          </div>
          {error && <p className="mt-2 text-xs text-amber-700">{error}</p>}
        </form>
      </div>
      </div>
    </div>
  );
}

function HomeChrome() {
  const { leftCollapsed, toggleLeft } = useShellChrome();
  if (!leftCollapsed) return null;
  return (
    <div className="hidden h-12 w-full shrink-0 items-center gap-2 border-b border-line/60 px-3 lg:flex">
      <button type="button" className={ICON_BTN} title="Open projects" onClick={toggleLeft}>
        <SidebarToggleIcon flipped />
      </button>
    </div>
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
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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

function SignInWall({
  name,
  email,
  setName,
  setEmail,
  onSubmit,
  busy,
  error,
}: {
  name: string;
  email: string;
  setName: (v: string) => void;
  setEmail: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string;
}) {
  return (
    <section className="glass-panel p-6 sm:p-8">
      <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted">Sign in</p>
      <h1 className="mt-2 text-[28px] font-semibold tracking-tight text-ink">CrewLane</h1>
      <p className="mt-2 text-sm text-muted">
        The AI does each phase&apos;s work. A named human accepts it before the project moves on.
      </p>
      <p className="mt-4 rounded-xl border border-line bg-well/80 px-3 py-2 text-xs text-muted">
        Phase 1: name and email create a local session (signed cookie). No password.
        Your display name is what the audit trail will record when you accept a gate.
      </p>
      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <input
          className="focus-ring rounded-xl border border-line bg-well px-3 py-2.5 text-sm"
          placeholder="Display name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="focus-ring rounded-xl border border-line bg-well px-3 py-2.5 text-sm"
          placeholder="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button
          type="submit"
          className="focus-ring rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-accent-ink disabled:opacity-50"
          disabled={busy || !name.trim() || !email.trim()}
        >
          {busy ? "Signing in…" : "Continue"}
        </button>
        {error && <p className="text-xs text-amber-700">{error}</p>}
      </form>
    </section>
  );
}
