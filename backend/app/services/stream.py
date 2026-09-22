"""AG-UI-style SSE events for chat transport (D48, D58).

On Postgres the graph runs in a worker thread with its own session while the
request thread polls for newly committed message rows and emits them as they
land - the read-back appears before the question, not after the whole turn.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.account import Account
from app.models.message import Message, max_seq
from app.models.project import Project
from app.schemas.api import MessageOut
from app.services import chat as chat_service

log = logging.getLogger(__name__)

POLL_SECONDS = 0.3


def _messages_after(
    session: Session, project: Project, after_seq: int, *, phase: str | None
) -> list[Message]:
    rows = list(
        session.scalars(
            select(Message)
            .where(Message.project_id == project.id, Message.seq > after_seq)
            .order_by(Message.seq.asc())
        ).all()
    )
    if not phase:
        return rows
    return [m for m in rows if m.phase == phase]


def stream_user_message_events(
    session: Session,
    project: Project,
    account: Account,
    *,
    content: str,
    skipped: bool,
    bound_to_question: bool = False,
    tab: str | None = None,
    skip_redirect_check: bool = False,
) -> Iterator[str]:
    """Yield SSE frames for a single user turn as the graph commits messages."""
    from app.services.chat_threads import live_tab

    emit_phase = tab or live_tab(project)
    yield _sse("RUN_STARTED", {})
    before = max_seq(session, project.id)

    if not get_settings().database_url.startswith("postgresql"):
        # ponytail: sqlite (tests) shares one connection across threads - run
        # synchronously there; live streaming is a Postgres-only behavior.
        chat_service.post_user_message(
            session,
            project,
            account,
            content=content,
            skipped=skipped,
            bound_to_question=bound_to_question,
            tab=tab,
            skip_redirect_check=skip_redirect_check,
        )
        for message in _messages_after(session, project, before, phase=emit_phase):
            yield _sse("MESSAGE", _payload(message))
        yield _sse("RUN_FINISHED", {})
        return

    errors: list[BaseException] = []

    def run() -> None:
        worker_session = get_session_factory()()
        try:
            worker_project = worker_session.get(Project, project.id)
            worker_account = worker_session.get(Account, account.id)
            chat_service.post_user_message(
                worker_session,
                worker_project,
                worker_account,
                content=content,
                skipped=skipped,
                bound_to_question=bound_to_question,
                tab=tab,
                skip_redirect_check=skip_redirect_check,
            )
        except BaseException as exc:  # surfaced after the drain below
            log.exception("graph worker failed during message stream")
            errors.append(exc)
        finally:
            worker_session.close()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    last = before
    while True:
        for message in _messages_after(session, project, last, phase=emit_phase):
            last = message.seq
            yield _sse("MESSAGE", _payload(message))
        if not worker.is_alive():
            break
        time.sleep(POLL_SECONDS)
    for message in _messages_after(session, project, last, phase=emit_phase):  # final drain
        last = message.seq
        yield _sse("MESSAGE", _payload(message))
    if errors:
        yield _sse("RUN_ERROR", {"message": str(errors[0])[:500]})
    yield _sse("RUN_FINISHED", {})


def _payload(message: Message) -> dict:
    return MessageOut.model_validate(message).model_dump(mode="json")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
