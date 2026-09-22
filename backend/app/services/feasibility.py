"""Feasibility research with cited web search (D24: advisory, never gating).

Runs automatically before the Planning gate (real-life planning researches
viability itself) and stays available as a manual query. The assessment
follows the teachingagile five dimensions (technical, economic, legal,
operational, schedule) and ends with a go/no-go recommendation.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.search import get_search
from app.agents.inference import PURPOSE_TAG, get_inference
from app.core.config import get_settings
from app.models.card import Card
from app.models.message import Message, max_seq
from app.models.project import Project
from app.services import cards as cards_service
from app.services.belief import SOURCE_KIND
from app.services.chat_threads import thread_key_for

FEASIBILITY_PROMPT = (
    "Assess project feasibility across the five classic dimensions - technical, "
    "economic, legal, operational, schedule - using ONLY the project facts and "
    "the search results below. Cite sources inline as (title, link). For any "
    "dimension the facts and results say nothing about, write 'not stated' - "
    "never guess. End with a one-line recommendation: 'Recommendation: GO' or "
    "'Recommendation: NO-GO', with a one-sentence reason. "
    "Advisory only - this never gates the project (D24)."
)


def run_feasibility(session: Session, project: Project, query: str) -> Message:
    if project.phase != "planning":
        raise ValueError("feasibility is only offered during Planning (D24)")

    settings = get_settings()
    hits = get_search(settings).search(query)
    sources_text = "\n".join(
        f"- {h['title']}: {h['snippet']} ({h['link']})" for h in hits
    )
    inference = get_inference(settings)
    summary = inference.complete(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": f"{PURPOSE_TAG} feasibility\n" + FEASIBILITY_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Project brief: {project.brief}\n\nQuery: {query}\n\nResults:\n{sources_text}"
                ),
            },
        ],
    )
    # Card carries a clean excerpt (word boundary, marked as such) - the gate
    # critic flagged the old mid-word cut as an unreviewable section. The full
    # report reaches the Charter via latest_report().
    excerpt = summary[:400].rsplit(" ", 1)[0] + (" […]" if len(summary) > 400 else "")
    cards_service.record_facts(
        session,
        project,
        area="general",
        facts=[f"Feasibility ({query}): {excerpt}"],
        source_message_id=f"feasibility:{query[:80]}",
    )
    message = Message(
        project_id=project.id,
        role="assistant",
        content=summary,
        widget={
            "type": "feasibility_report",
            "query": query,
            "summary": summary,
            "sources": hits,
        },
        seq=max_seq(session, project.id) + 1,
        phase="planning",
        thread_key=thread_key_for(project, phase="planning"),
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def _already_ran(session: Session, project: Project) -> bool:
    return (
        session.scalar(
            select(Card.id)
            .where(
                Card.project_id == project.id,
                Card.kind == SOURCE_KIND,
                Card.body.like("feasibility:%"),
            )
            .limit(1)
        )
        is not None
    )


def ensure_auto_feasibility(session: Session, project: Project) -> None:
    """Research feasibility once, automatically, before the Planning gate.

    Failures are reported loudly in chat and never block the gate - the
    research is advisory (D24), the honesty about failing is not optional.
    """
    if _already_ran(session, project):
        return
    query = f"feasibility of building: {project.brief[:140]}"
    try:
        run_feasibility(session, project, query)
    except Exception as exc:  # noqa: BLE001 - reported to the user, not hidden
        session.rollback()
        session.add(
            Message(
                project_id=project.id,
                role="assistant",
                content=f"Feasibility research failed and was skipped: {exc}",
                widget=None,
                seq=max_seq(session, project.id) + 1,
                phase="planning",
                thread_key=thread_key_for(project, phase="planning"),
            )
        )
        session.commit()


def latest_report(session: Session, project: Project) -> dict | None:
    """The most recent feasibility report widget, for document composition."""
    messages = session.scalars(
        select(Message)
        .where(Message.project_id == project.id, Message.role == "assistant")
        .order_by(Message.seq.desc())
    ).all()
    for message in messages:
        if message.widget and message.widget.get("type") == "feasibility_report":
            return message.widget
    return None
