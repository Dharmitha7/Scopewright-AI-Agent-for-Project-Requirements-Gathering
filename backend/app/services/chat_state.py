"""Read-only chat tab state (writable / mode / thread)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.graph import DONE_PHASE
from app.models.account import Account
from app.models.project import Project
from app.services import cards as cards_service
from app.services.chat_threads import live_tab, thread_key_for


def get_chat_state(
    session: Session,
    project: Project,
    account: Account,
    *,
    tab: str,
) -> dict[str, Any]:
    if tab not in ("planning", "requirements"):
        raise ValueError("tab must be planning or requirements")

    live = live_tab(project)
    # A reopened Planning redraft (D89) is also writable/live even though
    # project.phase stays on "requirements"/"done" throughout.
    redrafting = tab == "planning" and project.planning_redraft_active and live != "planning"
    writable = tab == live or redrafting
    phase_override = "planning" if redrafting else None
    thread_key = thread_key_for(project, phase=tab)

    if project.phase == DONE_PHASE and tab == "requirements":
        mode = "post_complete"
    elif not writable:
        mode = "interview"
    else:
        mode = _live_mode(session, project, account, phase_override=phase_override)

    result: dict[str, Any] = {
        "tab": tab,
        "writable": writable,
        "mode": mode,
        "thread_key": thread_key,
    }
    if tab == "requirements":
        result["requirements_stale_since"] = cards_service.requirements_stale_since(
            session, project
        )
    return result


def _live_mode(
    session: Session, project: Project, account: Account, *, phase_override: str | None = None
) -> str:
    from app.agents.runner import _graph

    graph, config = _graph(session, project, account, phase_override=phase_override)
    snap = graph.get_state(config)
    state = snap.values or {}
    gate_stage = str(state.get("gate_stage") or "").strip()
    if snap.interrupts and gate_stage:
        return "gate"
    return "interview"
