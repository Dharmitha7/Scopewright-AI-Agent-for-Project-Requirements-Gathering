"use client";

import { useEffect, useState } from "react";

const THEME_KEY = "crewlane.theme";

export type ThemeMode = "light" | "dark";

export function applyTheme(mode: ThemeMode) {
  document.documentElement.dataset.theme = mode;
  try {
    localStorage.setItem(THEME_KEY, mode);
  } catch {
    /* ignore */
  }
}

export function readTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  try {
    const v = localStorage.getItem(THEME_KEY);
    if (v === "dark" || v === "light") return v;
  } catch {
    /* ignore */
  }
  return "light";
}

/** Tiny client bootstrap so first paint respects saved theme. */
export function ThemeInit() {
  useEffect(() => {
    applyTheme(readTheme());
  }, []);
  return null;
}

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() =>
    typeof window === "undefined" ? "light" : readTheme(),
  );

  const toggle = () => {
    const next: ThemeMode = mode === "light" ? "dark" : "light";
    setMode(next);
    applyTheme(next);
  };

  return (
    <button
      type="button"
      className="focus-ring inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink hover:bg-canvas"
      title={mode === "light" ? "Dark mode" : "Light mode"}
      aria-label={mode === "light" ? "Switch to dark mode" : "Switch to light mode"}
      onClick={toggle}
    >
      {mode === "light" ? <MoonIcon /> : <SunIcon />}
    </button>
  );
}

function MoonIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
      />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" />
    </svg>
  );
}
