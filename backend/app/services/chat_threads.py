"""Chat tab thread keys. Must match LangGraph thread_id in runner._graph."""

from __future__ import annotations

from uuid import UUID

from app.models.project import Project

PLANNING_TAB = "planning"
REQUIREMENTS_TAB = "requirements"


def live_tab(project: Project) -> str:
    """The tab that owns the live interview — same as project.phase on main."""
    return PLANNING_TAB if project.phase == "planning" else REQUIREMENTS_TAB


def message_phase_for(project: Project, *, tab: str | None = None) -> str:
    """Phase stamped on new messages. Done maps to requirements (no third tab)."""
    chosen = tab or live_tab(project)
    if chosen == PLANNING_TAB:
        return "planning"
    return "requirements"


def planning_thread_key(project_id: UUID, version: int = 0) -> str:
    """version 0 (the original, pre-first-accept interview) keeps the legacy
    unversioned key so already-running/already-accepted projects' checkpoint
    and message threads don't shift under them (D89). A redraft only ever
    starts after the first accept (planning_doc_version >= 1), so version >= 1
    always names a genuinely new thread distinct from the original."""
    if version <= 0:
        return f"{project_id}:planning"
    return f"{project_id}:planning:v{int(version)}"


def requirements_thread_key(project_id: UUID, version: int) -> str:
    return f"{project_id}:requirements:v{int(version)}"


def thread_key_for(project: Project, *, phase: str | None = None) -> str:
    key = phase or message_phase_for(project)
    if key == "planning":
        return planning_thread_key(project.id, int(project.planning_doc_version or 0))
    return requirements_thread_key(
        project.id, int(project.requirements_doc_version or 0)
    )


def assert_tab_writable(project: Project, tab: str | None) -> str:
    """Return the tab whose thread should own this write - normally the live
    tab, but also Planning while a redraft is active (D89), even though
    project.phase stays on "requirements"/"done" throughout that window."""
    live = live_tab(project)
    if tab is None or tab == "":
        return live
    if tab not in (PLANNING_TAB, REQUIREMENTS_TAB):
        raise ValueError("tab must be planning or requirements")
    if tab == live:
        return live
    if tab == PLANNING_TAB:
        if project.planning_redraft_active:
            return PLANNING_TAB
        raise ValueError("Planning chat is read-only after the Charter is accepted")
    raise ValueError("Requirements chat is locked until the Charter is accepted")
