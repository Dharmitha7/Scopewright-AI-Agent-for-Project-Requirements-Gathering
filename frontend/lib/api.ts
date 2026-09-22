import type { MessageWidget } from "@/lib/widgets";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Account = {
  id: string;
  email: string;
  display_name: string;
};

export type Project = {
  id: string;
  name: string;
  brief: string;
  phase: string;
  planning_doc_version?: number;
  requirements_doc_version?: number;
  planning_redraft_active?: boolean;
  created_at: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  widget: MessageWidget | null;
  phase: string;
  thread_key: string;
  created_at: string;
};

export type ChatPhaseTab = "planning" | "requirements";

export type ChatState = {
  tab: ChatPhaseTab;
  writable: boolean;
  mode: "interview" | "gate" | "post_complete";
  thread_key: string;
  /** Set when Planning was accepted/redrafted after this Requirements
   * deliverable was last generated (D89) - null when not stale. */
  requirements_stale_since?: string | null;
};

export type GateAction = {
  action: "accept" | "revise" | "select_packs" | "redraft" | "planning_redraft";
  content?: string;
  area?: string;
  pack_ids?: string[];
  /** Ignored; Requirements is separate-only (D84). */
  pack_mode?: "separate";
  tab?: ChatPhaseTab;
};

export type Card = {
  id: string;
  kind: string;
  coverage_area: string | null;
  body: string;
  status: string;
  version: number;
  created_at: string;
  sources: string[];
};

export type Snapshot = {
  id: string;
  phase: string;
  document: string;
  body: string;
  narrative: string | null;
  narratives: {
    mode: "separate";
    packs: Record<string, string>;
    combined: string | null;
  } | null;
  accepted_by_account_id: string;
  created_at: string;
};

export type Upload = {
  id: string;
  filename: string;
  content_type: string;
  status: string;
  speaker_name: string | null;
  last_error: string | null;
  created_at: string;
};

export type ConflictItem = {
  id: string;
  card_a: { id: string; body: string; status: string };
  card_b: { id: string; body: string; status: string };
};

export type ConflictListResponse = {
  items: ConflictItem[];
};

export type ConflictAdvice = {
  pick: string;
  why: string;
  reply: string;
};

export type AuditEvent = {
  id: string;
  kind: string;
  actor: string;
  detail: Record<string, unknown>;
  created_at: string;
};

// Carries the real HTTP status alongside the message, so callers can tell a
// genuine 404 apart from a transient network/CORS/restart failure — plain
// `Error` swallowed the status into an unstructured string, which is why
// the project page used to treat every fetch failure as "not found"
// (see ProjectWorkspace's initial-load effect).
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || `${response.status}`, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || `${response.status}`, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<Account>("/auth/me"),
  devSession: (body: { display_name: string; email: string }) =>
    request<Account>("/auth/dev-session", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  microsoftStatus: () =>
    request<{
      configured: boolean;
      connected: boolean;
      local_mirror: boolean;
      connected_at: string | null;
    }>("/auth/microsoft/status"),
  microsoftDisconnect: () =>
    request<void>("/auth/microsoft/disconnect", { method: "POST" }),
  microsoftStartUrl: () => `${BASE}/auth/microsoft/start`,
  listProjects: () => request<Project[]>("/projects"),
  createProject: (brief: string, name?: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ brief, name: name || null }),
    }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  renameProject: (id: string, name: string) =>
    request<Project>(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  listMessages: (projectId: string, opts?: { phase?: ChatPhaseTab }) => {
    const qs = opts?.phase ? `?phase=${opts.phase}` : "";
    return request<Message[]>(`/projects/${projectId}/messages${qs}`);
  },
  getChatState: (projectId: string, tab: ChatPhaseTab) =>
    request<ChatState>(`/projects/${projectId}/chat-state?tab=${tab}`),
  postMessage: (
    projectId: string,
    body: {
      content?: string;
      skipped?: boolean;
      bound_to_question?: boolean;
      tab?: ChatPhaseTab;
      skip_redirect_check?: boolean;
    },
  ) =>
    request<Message[]>(`/projects/${projectId}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  postGate: (projectId: string, body: GateAction) =>
    request<Message[]>(`/projects/${projectId}/gate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listCards: (projectId: string) => request<Card[]>(`/projects/${projectId}/cards`),
  listSnapshots: (projectId: string) =>
    request<Snapshot[]>(`/projects/${projectId}/snapshots`),
  listUploads: (projectId: string) => request<Upload[]>(`/projects/${projectId}/uploads`),
  uploadFile: (projectId: string, file: File, speakerName?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (speakerName) form.append("speaker_name", speakerName);
    return requestForm<Upload>(`/projects/${projectId}/uploads`, form);
  },
  keepUpload: (projectId: string, uploadId: string) =>
    request<Upload>(`/projects/${projectId}/uploads/${uploadId}/keep`, { method: "POST" }),
  discardUpload: (projectId: string, uploadId: string) =>
    request<Upload>(`/projects/${projectId}/uploads/${uploadId}/discard`, { method: "POST" }),
  listConflicts: (projectId: string) =>
    request<ConflictListResponse>(`/projects/${projectId}/conflicts`),
  getConflictAdvice: (projectId: string, conflictId: string) =>
    request<ConflictAdvice>(`/projects/${projectId}/conflicts/${conflictId}/advice`),
  listAudit: (projectId: string) => request<AuditEvent[]>(`/projects/${projectId}/audit`),
  resolveConflict: (projectId: string, conflictId: string, winnerCardId: string) =>
    request<void>(`/projects/${projectId}/conflicts/${conflictId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ winner_card_id: winnerCardId }),
    }),
  runFeasibility: (projectId: string, query: string) =>
    request<Message>(`/projects/${projectId}/feasibility`, {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  updateCard: (projectId: string, cardId: string, body: string) =>
    request<Card>(`/projects/${projectId}/cards/${cardId}`, {
      method: "PATCH",
      body: JSON.stringify({ body }),
    }),
  retireCard: (projectId: string, cardId: string) =>
    request<void>(`/projects/${projectId}/cards/${cardId}/retire`, { method: "POST" }),
  ingestLink: (projectId: string, url: string) =>
    request<Upload>(`/projects/${projectId}/links`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  transcribe: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<{ text: string }>(`/projects/${projectId}/transcribe`, form);
  },
};

// Plain link target: the session cookie (SameSite=lax) rides along on
// top-level GET navigations, so a download link needs no fetch wrapper.
export function snapshotExportUrl(
  projectId: string,
  snapshotId: string,
  format: string,
  pack?: string,
): string {
  const base = `${BASE}/projects/${projectId}/snapshots/${snapshotId}/export?format=${format}`;
  return pack ? `${base}&pack=${encodeURIComponent(pack)}` : base;
}

/** Cookie-auth GET for Evidence preview of the original uploaded file (D82). */
export function uploadContentUrl(projectId: string, uploadId: string): string {
  return `${BASE}/projects/${projectId}/uploads/${uploadId}/content`;
}
