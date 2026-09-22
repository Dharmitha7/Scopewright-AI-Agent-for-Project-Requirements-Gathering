import type { Message } from "@/lib/api";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Handlers = {
  onStarted?: () => void;
  onMessage: (message: Message) => void;
  onFinished?: () => void;
  onError?: (message: string) => void;
};

function dispatchFrame(frame: string, handlers: Handlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;
  const data: unknown = JSON.parse(dataLines.join("\n"));
  if (event === "RUN_STARTED") handlers.onStarted?.();
  if (event === "MESSAGE") handlers.onMessage(data as Message);
  if (event === "RUN_ERROR") {
    const err = data as { message?: string };
    handlers.onError?.(err.message ?? "Something went wrong");
  }
  if (event === "RUN_FINISHED") handlers.onFinished?.();
}

export async function streamProjectMessage(
  projectId: string,
  body: {
    content?: string;
    skipped?: boolean;
    bound_to_question?: boolean;
    tab?: "planning" | "requirements";
    skip_redirect_check?: boolean;
  },
  handlers: Handlers,
): Promise<void> {
  const response = await fetch(`${BASE}/projects/${projectId}/messages/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    throw new Error((await response.text()) || `${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      dispatchFrame(buffer.slice(0, sep), handlers);
      buffer = buffer.slice(sep + 2);
      sep = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatchFrame(buffer, handlers);
}
