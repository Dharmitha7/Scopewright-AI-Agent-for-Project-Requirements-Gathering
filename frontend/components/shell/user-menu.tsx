"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Account } from "@/lib/api";

type MsStatus = {
  configured: boolean;
  connected: boolean;
  local_mirror: boolean;
  connected_at: string | null;
};

export function UserMenu({ account, collapsed }: { account: Account; collapsed?: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ms, setMs] = useState<MsStatus | null>(null);

  useEffect(() => {
    if (!open) return;
    void api.microsoftStatus().then(setMs).catch(() => setMs(null));
  }, [open]);

  const initials = account.display_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("") || "?";

  const signOut = async () => {
    setBusy(true);
    try {
      await api.logout();
      window.dispatchEvent(new Event("crewlane-auth"));
      router.push("/");
    } catch {
      setBusy(false);
    }
  };

  const disconnectOneDrive = async () => {
    setBusy(true);
    try {
      await api.microsoftDisconnect();
      setMs(await api.microsoftStatus());
    } catch {
      /* keep menu open */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        className={`focus-ring flex w-full items-center gap-2.5 rounded-xl px-2 py-2 text-left hover:bg-well/80 ${
          collapsed ? "justify-center" : ""
        }`}
        aria-expanded={open}
        title={account.display_name}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-semibold text-accent-ink">
          {initials}
        </span>
        {!collapsed && (
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
            {account.display_name}
          </span>
        )}
      </button>
      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
          />
          <div className="absolute bottom-full left-0 z-50 mb-2 w-full min-w-[12rem] rounded-xl border border-line bg-well p-1 shadow-lg">
            <p className="truncate px-3 py-2 text-xs text-muted" title={account.email}>
              {account.email}
            </p>
            {ms?.local_mirror ? (
              <p className="px-3 py-2 text-xs text-muted">OneDrive: local mirror</p>
            ) : ms?.connected ? (
              <button
                type="button"
                className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas disabled:opacity-50"
                disabled={busy}
                onClick={() => void disconnectOneDrive()}
              >
                Disconnect OneDrive
              </button>
            ) : ms?.configured ? (
              <a
                className="focus-ring block w-full rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas"
                href={api.microsoftStartUrl()}
              >
                Connect OneDrive
              </a>
            ) : null}
            <button
              type="button"
              className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas disabled:opacity-50"
              disabled={busy}
              onClick={() => void signOut()}
            >
              {busy ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
