"use client";

import Link from "next/link";
import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Account, Project } from "@/lib/api";
import { DeleteProjectDialog } from "@/components/shell/delete-project-dialog";
import { ICON_BTN } from "@/components/shell/app-shell";
import { SidebarToggleIcon } from "@/components/shell/sidebar-toggle-icon";
import { UserMenu } from "@/components/shell/user-menu";
import { ThemeToggle } from "@/components/shell/theme-toggle";

const LEFT_MIN = 208;
const LEFT_MAX = 360;

function MoreIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <circle cx="8" cy="3" r="1.25" />
      <circle cx="8" cy="8" r="1.25" />
      <circle cx="8" cy="13" r="1.25" />
    </svg>
  );
}

type ProjectRowProps = {
  project: Project;
  active: boolean;
  onCloseMobile?: () => void;
  onDelete: (id: string) => Promise<void>;
};

function ProjectRow({ project, active, onCloseMobile, onDelete }: ProjectRowProps) {
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  useLayoutEffect(() => {
    if (!menuOpen || !menuBtnRef.current) {
      setMenuPos(null);
      return;
    }
    const rect = menuBtnRef.current.getBoundingClientRect();
    setMenuPos({ top: rect.bottom + 4, left: rect.right });
  }, [menuOpen]);

  const confirmDelete = async () => {
    setBusy(true);
    try {
      await onDelete(project.id);
      setConfirmOpen(false);
      closeMenu();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div
        className={`group relative mb-0.5 flex items-stretch rounded-xl ${
          active ? "bg-accent" : "hover:bg-well/80"
        }`}
      >
        <Link
          href={`/projects/${project.id}`}
          title={project.name}
          onClick={onCloseMobile}
          className={`focus-ring min-w-0 flex-1 rounded-xl px-3 py-2 text-sm ${
            active ? "text-accent-ink" : "text-ink"
          }`}
        >
          <span className="block truncate pr-6 font-medium">{project.name}</span>
          <span
            className={`block truncate text-[10px] uppercase tracking-wide ${
              active ? "text-accent-ink/70" : "text-muted"
            }`}
          >
            {project.phase}
          </span>
        </Link>
        <div className="absolute right-1 top-1/2 -translate-y-1/2">
          <button
            ref={menuBtnRef}
            type="button"
            className={`${ICON_BTN} h-7 w-7 ${
              active
                ? "text-accent-ink/80 hover:bg-accent-ink/10 hover:text-accent-ink"
                : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
            }`}
            title="Project options"
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setMenuOpen((v) => !v);
            }}
          >
            <MoreIcon />
          </button>
          {menuOpen &&
            menuPos &&
            typeof document !== "undefined" &&
            createPortal(
              <>
                <button
                  type="button"
                  className="fixed inset-0 z-[90] cursor-default"
                  aria-label="Close menu"
                  onClick={closeMenu}
                />
                <div
                  role="menu"
                  className="fixed z-[91] min-w-[10rem] -translate-x-full rounded-xl border border-line bg-well p-1 shadow-lg"
                  style={{ top: menuPos.top, left: menuPos.left }}
                >
                  <button
                    type="button"
                    role="menuitem"
                    className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-danger hover:bg-canvas"
                    onClick={() => {
                      closeMenu();
                      setConfirmOpen(true);
                    }}
                  >
                    Delete project…
                  </button>
                </div>
              </>,
              document.body,
            )}
        </div>
      </div>
      {confirmOpen && (
        <DeleteProjectDialog
          name={project.name}
          busy={busy}
          onCancel={() => !busy && setConfirmOpen(false)}
          onConfirm={() => void confirmDelete()}
        />
      )}
    </>
  );
}

type Props = {
  account: Account;
  projects: Project[];
  selectedId?: string | null;
  collapsed: boolean;
  width: number;
  onToggleCollapsed: () => void;
  onCreate: () => void;
  onDeleteProject: (id: string) => Promise<void>;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
  onResizeStart: (e: React.MouseEvent) => void;
};

export function ProjectSidebar({
  account,
  projects,
  selectedId,
  collapsed,
  width,
  onToggleCollapsed,
  onCreate,
  onDeleteProject,
  mobileOpen = false,
  onCloseMobile,
  onResizeStart,
}: Props) {
  const rail = (
    <aside
      className="relative flex h-full min-h-0 flex-col border-r border-line/80 bg-glass/90 backdrop-blur-md"
      style={{ width, minWidth: LEFT_MIN, maxWidth: LEFT_MAX }}
    >
      <div className="flex h-12 shrink-0 items-center gap-2 px-3">
        <Link
          href="/"
          className="focus-ring flex min-w-0 flex-1 items-center gap-2.5 rounded-md"
          onClick={onCloseMobile}
        >
          <span className="block h-[18px] w-[18px] shrink-0 rounded-[5px] bg-accent" />
          <span className="truncate text-sm font-semibold tracking-tight text-ink">CrewLane</span>
        </Link>
        <button
          type="button"
          className="focus-ring inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-well hover:text-ink"
          title="Collapse sidebar"
          onClick={onToggleCollapsed}
        >
          <SidebarToggleIcon />
        </button>
      </div>

      <div className="mt-3 flex shrink-0 items-center gap-2 px-3 pb-2">
        <p className="flex-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
          Projects
        </p>
        <button
          type="button"
          className="focus-ring flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-well text-lg leading-none text-ink hover:border-accent/30"
          title="New project"
          onClick={onCreate}
        >
          +
        </button>
      </div>

      <nav className="sidebar-scroll min-h-0 flex-1 px-2 pb-2" aria-label="Projects">
        {projects.length === 0 && (
          <p className="px-2 py-2 text-xs text-muted">No projects yet.</p>
        )}
        {projects.map((p) => (
          <ProjectRow
            key={p.id}
            project={p}
            active={p.id === selectedId}
            onCloseMobile={onCloseMobile}
            onDelete={onDeleteProject}
          />
        ))}
      </nav>

      <div className="flex shrink-0 items-center gap-1 border-t border-line p-2">
        <div className="min-w-0 flex-1">
          <UserMenu account={account} />
        </div>
        <ThemeToggle />
      </div>

      <div
        role="separator"
        aria-orientation="vertical"
        title="Drag to resize"
        className="absolute inset-y-0 right-0 z-10 hidden w-1 cursor-col-resize hover:bg-accent/20 lg:block"
        onMouseDown={onResizeStart}
      />
    </aside>
  );

  return (
    <>
      {!collapsed && <div className="relative hidden h-full shrink-0 lg:block">{rail}</div>}

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink/40"
            aria-label="Close sidebar"
            onClick={onCloseMobile}
          />
          <div className="absolute inset-y-0 left-0 shadow-xl">{rail}</div>
        </div>
      )}
    </>
  );
}
