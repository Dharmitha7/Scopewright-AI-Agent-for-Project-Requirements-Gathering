"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Account } from "@/lib/api";

export function AppHeader({ subtitle }: { subtitle?: string }) {
  const router = useRouter();
  const [account, setAccount] = useState<Account | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api
        .me()
        .then((me) => {
          if (!cancelled) setAccount(me);
        })
        .catch(() => {
          if (!cancelled) setAccount(null);
        });
    void load();
    window.addEventListener("crewlane-auth", load);
    return () => {
      cancelled = true;
      window.removeEventListener("crewlane-auth", load);
    };
  }, []);

  const signOut = async () => {
    setBusy(true);
    try {
      await api.logout();
      router.push("/");
    } catch {
      setBusy(false);
    }
  };

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line/80 bg-glass px-5 backdrop-blur-md supports-[backdrop-filter]:bg-glass/90">
      <Link href="/" className="focus-ring flex shrink-0 items-center gap-2.5 rounded-md">
        <span className="block h-[18px] w-[18px] rounded-[5px] bg-accent" />
        <span className="text-sm font-semibold tracking-tight text-ink">CrewLane</span>
      </Link>
      {subtitle ? (
        <span
          className="min-w-0 flex-1 truncate text-sm font-medium text-ink"
          title={subtitle}
        >
          {subtitle}
        </span>
      ) : (
        <span className="hidden flex-1 text-xs text-muted sm:inline" title="agents draft · humans decide">
          agents draft · humans decide
        </span>
      )}
      {account && (
        <div className="ml-auto flex shrink-0 items-center gap-3">
          <span className="max-w-[10rem] truncate text-xs text-muted" title={account.display_name}>
            {account.display_name}
          </span>
          <button
            type="button"
            className="focus-ring rounded-md px-2 py-1 text-xs text-muted hover:bg-well hover:text-ink disabled:opacity-50"
            disabled={busy}
            onClick={() => void signOut()}
          >
            {busy ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </header>
  );
}
