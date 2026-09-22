"""Chat spine (D10, D46): every message enters the phase graph; replies land
as message rows written by the graph. The mock interviewer is gone."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import SKIP_LABEL
from app.agents.runner import ensure_phase_started, handle_gate_action, handle_user_message
from app.models.account import Account
from app.models.message import Message
from app.models.project import Project
from app.services import ingestion as ingestion_service
from app.services.chat_threads import live_tab


def _all_messages(session: Session, project: Project) -> list[Message]:
    return list(
        session.scalars(
            select(Message).where(Message.project_id == project.id).order_by(Message.seq.asc())
        ).all()
    )


def _filter_messages(
    messages: list[Message],
    project: Project,
    *,
    phase: str | None,
) -> list[Message]:
    tab = phase or live_tab(project)
    return [m for m in messages if m.phase == tab]


def list_messages(
    session: Session,
    project: Project,
    account: Account,
    *,
    phase: str | None = None,
) -> list[Message]:
    # Ingest-first opening (stop-2 decision): the interview only starts once
    # front-door intake is fully read, so the read-back and first question
    # are grounded in the evidence instead of preceding it.
    tab = phase or live_tab(project)
    if tab not in ("planning", "requirements"):
        raise ValueError("phase must be planning or requirements")
    if not ingestion_service.has_pending_intake(session, project) and tab == live_tab(project):
        ensure_phase_started(session, project, account)
    return _filter_messages(_all_messages(session, project), project, phase=tab)


def post_user_message(
    session: Session,
    project: Project,
    account: Account,
    *,
    content: str,
    skipped: bool = False,
    bound_to_question: bool = False,
    tab: str | None = None,
    skip_redirect_check: bool = False,
) -> list[Message]:
    text = SKIP_LABEL if skipped else content.strip()
    out_tab = tab or live_tab(project)
    handle_user_message(
        session,
        project,
        account,
        content=text,
        skipped=skipped,
        bound_to_question=bound_to_question,
        tab=tab,
        skip_redirect_check=skip_redirect_check,
    )
    session.refresh(project)
    return _filter_messages(_all_messages(session, project), project, phase=out_tab)


def post_gate_action(
    session: Session,
    project: Project,
    account: Account,
    *,
    action: str,
    content: str = "",
    area: str | None = None,
    pack_ids: list[str] | None = None,
    pack_mode: str | None = None,
    tab: str | None = None,
) -> list[Message]:
    # Capture the tab before accept advances project.phase.
    out_tab = tab or live_tab(project)
    handle_gate_action(
        session,
        project,
        account,
        action=action,
        content=content,
        area=area,
        pack_ids=pack_ids,
        pack_mode=pack_mode,
        tab=tab,
    )
    session.refresh(project)
    if action == "redraft":
        out_tab = "requirements"
    return _filter_messages(_all_messages(session, project), project, phase=out_tab)
