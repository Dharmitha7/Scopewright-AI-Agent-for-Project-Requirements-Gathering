"""Knowledge seam between the graph and storage (D17/D22).

CardKnowledge replaces the interim MessageKnowledge: facts land as real
cards + supported-by strings in Postgres (app/services/cards.py), not only as
widgets on chat messages. The graph never touches tables directly and never
changed - it still only calls say / record_facts / planning_digest.
"""

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message, max_seq
from app.models.project import Project
from app.services import cards as cards_service
from app.services import rag_traces
from app.services.chat_threads import message_phase_for, thread_key_for
from app.services.retrieval import RetrievalResult, retrieve


class KnowledgePort(Protocol):
    def say(self, content: str, widget: dict[str, Any] | None = None) -> str: ...
    def record_facts(
        self, area: str, facts: list[str], source_message_id: str
    ) -> list[dict[str, Any]]: ...
    def planning_digest(self) -> str: ...
    def area_facts(self, area: str) -> list[str]: ...
    def retrieve(self, query: str) -> RetrievalResult: ...
    def trace_retrieval_decision(self, detail: dict[str, Any]) -> None: ...


class CardKnowledge:
    """KnowledgePort backed by real cards/strings/snapshots (D22).

    record_facts() is silent storage: it returns conflict_card widgets for the
    graph to emit, so each user turn costs one LLM call and one reply.
    """

    def __init__(
        self,
        session: Session,
        project: Project,
        *,
        phase: str | None = None,
        thread_key: str | None = None,
    ) -> None:
        self._session = session
        self._project = project
        self._phase = phase or message_phase_for(project)
        self._thread_key = thread_key or thread_key_for(project, phase=self._phase)

    def say(self, content: str, widget: dict[str, Any] | None = None) -> str:
        message = Message(
            project_id=self._project.id,
            role="assistant",
            content=content,
            widget=widget,
            seq=max_seq(self._session, self._project.id) + 1,
            phase=self._phase,
            thread_key=self._thread_key,
        )
        self._session.add(message)
        self._session.commit()
        self._session.refresh(message)
        return str(message.id)

    def record_facts(
        self, area: str, facts: list[str], source_message_id: str
    ) -> list[dict[str, Any]]:
        if not facts:
            return []
        _created, outcomes = cards_service.record_facts(
            self._session,
            self._project,
            area=area,
            facts=facts,
            source_message_id=source_message_id,
        )
        return [
            cards_service.conflict_card_widget(
                conflict_id=meta["conflict_id"],
                card=card,
                other_card_id=meta["other_card_id"],
                other_body=meta["other_body"],
            )
            for card, outcome, meta in outcomes
            if outcome == "conflict" and meta
        ]

    def posted_conflict_ids(self) -> set[str]:
        rows = self._session.scalars(
            select(Message).where(
                Message.project_id == self._project.id,
                Message.role == "assistant",
            )
        ).all()
        ids: set[str] = set()
        for message in rows:
            widget = message.widget
            if isinstance(widget, dict) and widget.get("type") == "conflict_card":
                cid = str(widget.get("conflict_id") or "").strip()
                if cid:
                    ids.add(cid)
        return ids

    def emit_open_conflict_cards(self, conflicts: list[dict[str, Any]]) -> int:
        """Conflicts resolve in the composer strip (listConflicts), not chat."""
        return 0

    def planning_digest(self) -> str:
        lines = [f"Project brief: {self._project.brief}"]
        lines.extend(cards_service.digest_lines(self._session, self._project))
        return "\n".join(lines)

    def area_facts(self, area: str) -> list[str]:
        return cards_service.area_facts(self._session, self._project, area)

    def retrieve(self, query: str) -> RetrievalResult:
        """Retrieve structured hits and persist an inspectable execution trace."""
        result = retrieve(self._session, self._project.id, query)
        rag_traces.record(
            self._session,
            project_id=self._project.id,
            kind="execution",
            query=query,
            detail=result.model_dump()["trace"],
        )
        return result

    def trace_retrieval_decision(self, detail: dict[str, Any]) -> None:
        rag_traces.record(
            self._session,
            project_id=self._project.id,
            kind="decision",
            query=str(detail.get("query") or ""),
            detail=detail,
        )


def user_message(
    session: Session,
    project: Project,
    content: str,
    *,
    phase: str | None = None,
    thread_key: str | None = None,
) -> Message:
    msg_phase = phase or message_phase_for(project)
    msg_thread = thread_key or thread_key_for(project, phase=msg_phase)
    message = Message(
        project_id=project.id,
        role="user",
        content=content,
        widget=None,
        seq=max_seq(session, project.id) + 1,
        phase=msg_phase,
        thread_key=msg_thread,
    )
    session.add(message)
    session.commit()
    return message
