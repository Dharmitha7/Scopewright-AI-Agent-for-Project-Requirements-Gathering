"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import type { Account, Project } from "@/lib/api";
import { ProjectSidebar } from "@/components/shell/project-sidebar";
import { api } from "@/lib/api";
import { SidebarToggleIcon } from "@/components/shell/sidebar-toggle-icon";
import { HamburgerIcon } from "@/components/shell/hamburger-icon";
import type { WorkspaceTab } from "@/components/shell/context-tabs";

const LEFT_COLLAPSE_KEY = "crewlane.sidebarCollapsed";
const RIGHT_OPEN_KEY = "crewlane.rightSidebarOpen.v3";
const LEFT_WIDTH_KEY = "crewlane.leftWidth";
const RIGHT_WIDTH_KEY = "crewlane.rightWidth";

export const LEFT_MIN = 208;
export const LEFT_MAX = 360;
export const RIGHT_MIN = 296;
export const RIGHT_MAX = 480;

const TAB_ORDER: WorkspaceTab[] = ["artifacts", "coverage", "audit", "knowledge"];

export const ICON_BTN =
  "focus-ring inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line bg-well/95 text-muted shadow-sm hover:text-ink";

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
    </svg>
  );
}

type ShellChrome = {
  leftCollapsed: boolean;
  rightOpen: boolean;
  toggleLeft: () => void;
  closeRight: () => void;
  openRightTab: (tab: WorkspaceTab) => void;
};

const ShellChromeContext = createContext<ShellChrome | null>(null);
const CreateProjectContext = createContext<() => void>(() => {});

export function useShellChrome(): ShellChrome {
  const ctx = useContext(ShellChromeContext);
  if (!ctx) {
    return {
      leftCollapsed: false,
      rightOpen: false,
      toggleLeft: () => {},
      closeRight: () => {},
      openRightTab: () => {},
    };
  }
  return ctx;
}

export function useOpenCreateProject() {
  return useContext(CreateProjectContext);
}

function readFlag(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  try {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    return v === "1";
  } catch {
    return fallback;
  }
}

function writeFlag(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

function readWidth(key: string, fallback: number, min: number, max: number): number {
  if (typeof window === "undefined") return fallback;
  try {
    const n = Number(localStorage.getItem(key));
    if (!Number.isFinite(n)) return fallback;
    return Math.min(max, Math.max(min, n));
  } catch {
    return fallback;
  }
}

function writeWidth(key: string, value: number) {
  try {
    localStorage.setItem(key, String(Math.round(value)));
  } catch {
    /* ignore */
  }
}

/** Hamburger → 4-tab dropdown. Always opens the menu (also while panel is open). */
export function RightPanelMenu({
  labels,
  align = "right",
}: {
  labels: Record<WorkspaceTab, string>;
  align?: "left" | "right";
}) {
  const { openRightTab } = useShellChrome();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        className={ICON_BTN}
        title="Switch panel"
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((v) => !v)}
      >
        <HamburgerIcon />
      </button>
      {menuOpen && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default"
            aria-label="Close menu"
            onClick={() => setMenuOpen(false)}
          />
          <div
            className={`absolute top-full z-50 mt-1 min-w-[10rem] rounded-xl border border-line bg-well p-1 shadow-lg ${
              align === "right" ? "right-0" : "left-0"
            }`}
          >
            {TAB_ORDER.map((key) => (
              <button
                key={key}
                type="button"
                className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas"
                onClick={() => {
                  openRightTab(key);
                  setMenuOpen(false);
                }}
              >
                {labels[key]}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

type Props = {
  account: Account;
  projects: Project[];
  selectedProjectId?: string | null;
  onProjectsRefresh?: () => void;
  rightTab?: WorkspaceTab;
  onRightTabChange?: (tab: WorkspaceTab) => void;
  rightTabLabels?: Record<WorkspaceTab, string>;
  rightPanel?: ReactNode;
  children: ReactNode;
};

export function AppShell({
  account,
  projects,
  selectedProjectId,
  onProjectsRefresh,
  rightTab = "artifacts",
  onRightTabChange,
  rightTabLabels,
  rightPanel,
  children,
}: Props) {
  const router = useRouter();
  const [leftCollapsed, setLeftCollapsed] = useState(() => readFlag(LEFT_COLLAPSE_KEY, false));
  const [rightOpen, setRightOpen] = useState(() => readFlag(RIGHT_OPEN_KEY, false));
  const [leftWidth, setLeftWidth] = useState(() =>
    readWidth(LEFT_WIDTH_KEY, LEFT_MIN, LEFT_MIN, LEFT_MAX),
  );
  const [rightWidth, setRightWidth] = useState(() =>
    readWidth(RIGHT_WIDTH_KEY, RIGHT_MIN, RIGHT_MIN, RIGHT_MAX),
  );
  const [mobileNav, setMobileNav] = useState(false);
  const [mobileRight, setMobileRight] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const goHomeCreate = () => {
    if (selectedProjectId) router.push("/");
  };

  const handleDeleteProject = useCallback(
    async (projectId: string) => {
      await api.deleteProject(projectId);
      if (selectedProjectId === projectId) router.push("/");
      onProjectsRefresh?.();
    },
    [onProjectsRefresh, router, selectedProjectId],
  );

  const toggleLeft = useCallback(() => {
    setLeftCollapsed((prev) => {
      const next = !prev;
      writeFlag(LEFT_COLLAPSE_KEY, next);
      return next;
    });
  }, []);

  const closeRight = useCallback(() => {
    setRightOpen(false);
    writeFlag(RIGHT_OPEN_KEY, false);
    setMobileRight(false);
  }, []);

  const openRightTab = useCallback(
    (tab: WorkspaceTab) => {
      onRightTabChange?.(tab);
      setRightOpen(true);
      writeFlag(RIGHT_OPEN_KEY, true);
      setMobileRight(true);
      setMobileMenuOpen(false);
    },
    [onRightTabChange],
  );

  const chrome = useMemo<ShellChrome>(
    () => ({ leftCollapsed, rightOpen, toggleLeft, closeRight, openRightTab }),
    [leftCollapsed, rightOpen, toggleLeft, closeRight, openRightTab],
  );

  const labels = rightTabLabels ?? {
    artifacts: "Artifacts",
    coverage: "Checklist",
    audit: "Audit",
    knowledge: "Knowledge",
  };
  const panelTitle = labels[rightTab];
  const hasRightPanel = Boolean(rightPanel);

  const startDrag = (side: "left" | "right", e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = side === "left" ? leftWidth : rightWidth;
    let live = startW;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - startX;
      if (side === "left") {
        live = Math.min(LEFT_MAX, Math.max(LEFT_MIN, startW + dx));
        setLeftWidth(live);
      } else {
        live = Math.min(RIGHT_MAX, Math.max(RIGHT_MIN, startW - dx));
        setRightWidth(live);
      }
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      writeWidth(side === "left" ? LEFT_WIDTH_KEY : RIGHT_WIDTH_KEY, live);
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  };

  return (
    <CreateProjectContext.Provider value={goHomeCreate}>
      <ShellChromeContext.Provider value={chrome}>
        <div className="relative flex h-dvh min-h-0 overflow-hidden">
          <ProjectSidebar
            account={account}
            projects={projects}
            selectedId={selectedProjectId}
            collapsed={leftCollapsed}
            width={leftWidth}
            onToggleCollapsed={toggleLeft}
            onCreate={goHomeCreate}
            onDeleteProject={handleDeleteProject}
            mobileOpen={mobileNav}
            onCloseMobile={() => setMobileNav(false)}
            onResizeStart={(e) => startDrag("left", e)}
          />

          <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="relative flex h-12 shrink-0 items-center gap-2 border-b border-line/60 px-3 lg:hidden">
              <button
                type="button"
                className={ICON_BTN}
                onClick={() => setMobileNav(true)}
                title="Menu"
              >
                <SidebarToggleIcon flipped />
              </button>
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">CrewLane</span>
              {hasRightPanel && (
                <button
                  type="button"
                  className={ICON_BTN}
                  title="Context"
                  onClick={() => setMobileMenuOpen((v) => !v)}
                >
                  <HamburgerIcon />
                </button>
              )}
              {mobileMenuOpen && hasRightPanel && (
                <>
                  <button
                    type="button"
                    className="fixed inset-0 z-40 cursor-default"
                    aria-label="Close menu"
                    onClick={() => setMobileMenuOpen(false)}
                  />
                  <div className="absolute right-3 top-12 z-50 min-w-[10rem] rounded-xl border border-line bg-well p-1 shadow-lg">
                    {TAB_ORDER.map((key) => (
                      <button
                        key={key}
                        type="button"
                        className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas"
                        onClick={() => openRightTab(key)}
                      >
                        {labels[key]}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="relative flex min-h-0 min-w-0 flex-1">
              <main className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                {children}
              </main>

              {hasRightPanel && rightOpen && (
                <div
                  className="relative hidden h-full shrink-0 border-l border-line/80 bg-glass/70 backdrop-blur-md lg:flex lg:flex-col"
                  style={{ width: rightWidth }}
                >
                  <div
                    role="separator"
                    aria-orientation="vertical"
                    title="Drag to resize"
                    className="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize hover:bg-accent/20"
                    onMouseDown={(e) => startDrag("right", e)}
                  />
                  <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line/60 px-3">
                    <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                      {panelTitle}
                    </p>
                    <RightPanelMenu labels={labels} />
                    <button
                      type="button"
                      className={ICON_BTN}
                      title="Close panel"
                      onClick={closeRight}
                    >
                      <CloseIcon />
                    </button>
                  </div>
                  <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{rightPanel}</div>
                </div>
              )}

              {hasRightPanel && mobileRight && (
                <div className="fixed inset-0 z-40 lg:hidden">
                  <button
                    type="button"
                    className="absolute inset-0 bg-ink/40"
                    aria-label="Close context"
                    onClick={() => setMobileRight(false)}
                  />
                  <div className="absolute inset-y-0 right-0 w-[min(100%,296px)] border-l border-line bg-well shadow-xl">
                    <div className="flex h-12 items-center justify-between gap-2 px-3">
                      <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                        {panelTitle}
                      </p>
                      <RightPanelMenu labels={labels} />
                      <button
                        type="button"
                        className="focus-ring rounded-lg border border-line px-2 py-1 text-xs text-muted"
                        onClick={() => setMobileRight(false)}
                      >
                        Close
                      </button>
                    </div>
                    <div className="flex h-[calc(100%-48px)] min-h-0 flex-col overflow-hidden">
                      {rightPanel}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </ShellChromeContext.Provider>
    </CreateProjectContext.Provider>
  );
}
