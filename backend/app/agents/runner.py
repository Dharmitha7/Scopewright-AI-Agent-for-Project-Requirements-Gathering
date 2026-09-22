"""Runs the phase graph for a project (D45/D46).

Transport-agnostic: everything user-visible is written to the messages table
by the graph, so the REST endpoints (today) and the AG-UI stream (frontend
lane, next) both just read messages. thread_id = "<project_id>:<phase>".
"""

from __future__ import annotations

import threading
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agents.graph import (
    ANSWERED,
    DONE_PHASE,
    build_phase_graph,
    initial_state,
    question_card_widget,
)
from app.agents.inference import PURPOSE_TAG, complete_json, get_inference, parse_json_object
from app.agents.knowledge import CardKnowledge, user_message
from app.agents.templates import get_template
from app.core.config import get_settings
from app.models.account import Account
from app.models.project import Project
from app.services import audit as audit_service
from app.services import belief as belief_service
from app.services import cards as cards_service
from app.services import documents as documents_service
from app.services import feasibility as feasibility_service
from app.services import ingestion as ingestion_service
from app.services import onedrive as onedrive_service
from app.services.chat_threads import (
    PLANNING_TAB,
    assert_tab_writable,
    message_phase_for,
    planning_thread_key,
    thread_key_for,
)
from app.services.draft_changelog import draft_change_bullets, prepend_changelog, strip_changelog
from app.services.rag import (
    SEARCH_EVIDENCE_TOOL,
    augment_context,
    enforce_grounding,
    grounding_rules,
    scope_refusal_reply,
)

_memory_saver = InMemorySaver()
_postgres_saver = None
_saver_lock = threading.Lock()

# Neutral "nothing on record" fallback for post-complete free chat, mirrors
# graph.py's mid-interview aside fallback (same failure mode: the model
# returned no usable text). Never a specific, wrong instruction like the old
# "Use Redraft requirements..." string this replaces - that string was a
# generic empty-reply filler worded around the wrong sub-case, so it read as
# a deliberate (and wrong) answer instead of what it actually was.
POST_COMPLETE_NO_ANSWER_REPLY = "That is not stated anywhere yet."


def init_checkpointer() -> None:
    """Run PostgresSaver.setup() once at startup (before concurrent requests)."""
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        return
    global _postgres_saver
    with _saver_lock:
        if _postgres_saver is not None:
            return
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        pool = ConnectionPool(
            url,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
            min_size=1,
            max_size=5,
        )
        pool.open(wait=True, timeout=10)
        saver = PostgresSaver(pool)
        saver.setup()
        _postgres_saver = saver


def _checkpointer():
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        return _memory_saver
    if _postgres_saver is None:
        return _memory_saver
    return _postgres_saver


def _last_requirements_packs(session: Session, project: Project) -> dict[str, str]:
    snaps = cards_service.list_snapshots(session, project)
    for snap in reversed(snaps):
        if snap.phase == "requirements" and snap.narratives and snap.narratives.get("packs"):
            return dict(snap.narratives["packs"])
    return {}


def _graph(
    session: Session, project: Project, account: Account, *, phase_override: str | None = None
):
    settings = get_settings()
    # A Planning redraft (D89) builds the Planning template/graph while
    # project.phase stays on "requirements"/"done" - phase_override is the
    # only thing that tells this function which graph to build in that case.
    redrafting_planning = phase_override == "planning" and project.phase != "planning"
    # Redraft keeps phase=requirements while generating; done uses post_complete.
    phase_key = phase_override or (project.phase if project.phase != DONE_PHASE else "requirements")
    template = get_template(phase_key)

    def on_accept(pending: dict | None = None) -> None:
        snapshot = cards_service.freeze_snapshot(session, project, template, account.id)
        if pending and pending.get("packs"):
            packs = dict(pending["packs"])
            # Finals never carry draft changelog (D83).
            packs = {k: strip_changelog(v) for k, v in packs.items()}
            documents_service.attach_pack_narratives(
                session,
                snapshot,
                mode="separate",
                packs=packs,
            )
            project.requirements_doc_version = int(project.requirements_doc_version or 0) + 1
            onedrive_service.sync_requirements_final(
                session,
                project,
                project.requirements_doc_version,
                packs,
            )
        else:
            documents_service.generate_narrative(session, project, snapshot, template)
            body = strip_changelog(snapshot.narrative or "")
            project.planning_doc_version = int(project.planning_doc_version or 0) + 1
            ver = project.planning_doc_version
            onedrive_service.sync_planning_draft(session, project, ver, body)
            onedrive_service.sync_planning_final(session, project, ver, body)
        if redrafting_planning:
            # A redraft's re-accept never advances phase - it's a side
            # excursion, not a re-run of the pipeline (D89). Un-completing a
            # DONE project as a side effect of fixing one Planning fact would
            # be a much worse bug than the one this feature fixes.
            project.planning_redraft_active = False
        else:
            project.phase = template.next_phase or DONE_PHASE
        session.commit()

    on_gate_research = None
    if template.auto_research:

        def on_gate_research() -> None:
            feasibility_service.ensure_auto_feasibility(session, project)

    def on_compose_packs(pack_keys: list[str], mode: str) -> dict:
        previous = _last_requirements_packs(session, project)
        composed = documents_service.compose_selected_packs(
            session,
            project,
            template,
            pack_keys=pack_keys,
            mode="separate",
            critic_issues=None,
        )
        packs = dict(composed.get("packs") or {})
        annotated: dict[str, str] = {}
        from app.agents.deliverables import PACK_BY_KEY

        for key, body in packs.items():
            title = PACK_BY_KEY[key].title if key in PACK_BY_KEY else key
            bullets = draft_change_bullets(
                settings,
                pack_title=title,
                previous=previous.get(key) or "",
                current=body,
            )
            annotated[key] = prepend_changelog(body, bullets)
        composed["packs"] = annotated
        display = "\n\n---\n\n".join(annotated.values())
        composed["display"] = display
        composed["teaser"] = display[:1200]
        onedrive_service.sync_requirements_draft(session, project, annotated)
        return composed

    def on_apply_critic_findings(composed: dict, critic_issues: list) -> dict:
        updated = documents_service.apply_critic_findings(
            session, project, template, composed, critic_issues
        )
        onedrive_service.sync_requirements_draft(
            session, project, dict(updated.get("packs") or {})
        )
        return updated

    if phase_key == "planning":
        # version 0 (pre-first-accept) keeps the legacy unversioned thread;
        # a redraft (planning_doc_version >= 1) always gets its own new one.
        thread_id = planning_thread_key(project.id, int(project.planning_doc_version or 0))
    else:
        # New thread per requirements version so redraft is a clean gate (D83).
        thread_id = f"{project.id}:requirements:v{int(project.requirements_doc_version or 0)}"
    return build_phase_graph(
        template=get_template(phase_key),
        knowledge=CardKnowledge(
            session, project, phase=phase_key, thread_key=thread_id
        ),
        inference=get_inference(settings),
        model=settings.groq_model,
        display_name=account.display_name,
        on_accept=on_accept,
        checkpointer=_checkpointer(),
        # Also naturally skips auto-research during a Planning redraft (D89):
        # phase_key ("planning") != project.phase ("requirements"/"done")
        # then, so paid research never silently re-runs on a redraft.
        on_gate_research=on_gate_research if phase_key == project.phase else None,
        on_compose_packs=on_compose_packs if phase_key == "requirements" else None,
        on_apply_critic_findings=on_apply_critic_findings
        if phase_key == "requirements"
        else None,
        list_open_conflicts=lambda: belief_service.list_conflicts(session, project),
        on_resolve_conflict=lambda cid, winner: belief_service.resolve_conflict(
            session, project, UUID(cid), UUID(winner)
        ),
    ), {"configurable": {"thread_id": thread_id}}


def ensure_phase_started(
    session: Session, project: Project, account: Account, *, phase_override: str | None = None
) -> None:
    if phase_override is None and project.phase == DONE_PHASE:
        return
    graph, config = _graph(session, project, account, phase_override=phase_override)
    if not graph.get_state(config).values:
        graph.invoke(initial_state(get_template(phase_override or project.phase)), config)


def _phase_override_for_tab(project: Project, tab: str) -> str | None:
    """None means "use project.phase as usual." "planning" means the caller
    is writing to a reopened Planning redraft (D89) even though project.phase
    is still "requirements"/"done"."""
    if tab == PLANNING_TAB and project.phase != "planning":
        if not project.planning_redraft_active:
            raise ValueError("Planning is not open for editing")
        return "planning"
    return None


def handle_post_complete_message(
    session: Session,
    project: Project,
    account: Account,
    *,
    content: str,
    source_message_id: str = "",
) -> None:
    """Free-form chat after Requirements Accept (D83) — no coverage interview,
    but the same D81 bounded-tool-call grounding/scope guardrail as the
    interview turn node, so this path can no longer answer fully unguarded.

    A DONE project previously had no way to record a genuinely new fact at
    all here — every message was treated as a question to answer from what
    already exists, so a real statement ("we should support multi-user
    login") got run through the Q&A/grounding path, found nothing to verify
    it against, and came back as a failed lookup instead of being recorded
    (D90). The schema below adds intent/area/facts so a declarative message
    can be routed to the same record_facts() funnel the interview uses,
    instead of only ever being asked-and-answered.
    """
    settings = get_settings()
    knowledge = CardKnowledge(
        session,
        project,
        phase=message_phase_for(project),
        thread_key=thread_key_for(project),
    )
    digest = knowledge.planning_digest()
    inference = get_inference(settings)
    model = settings.groq_model
    area_keys = {a.key for a in get_template("planning").areas} | {
        a.key for a in get_template("requirements").areas
    }
    area_guidance = "\n".join(
        f"- {a.key}: {a.guidance}"
        for a in (*get_template("planning").areas, *get_template("requirements").areas)
    )
    system_base = (
        PURPOSE_TAG
        + "post_complete_turn\n"
        + "You are CrewLane after the Requirements gate was accepted. "
        "Answer free-form questions using the project cards below. Do not "
        "restart the interview.\n"
        "intent is 'answer' ONLY when the user states a NEW product fact/requirement "
        "not yet in the facts below - e.g. 'we should support multi-user login'. "
        "When intent is 'answer', set facts to the new statement(s) and area to "
        "the single best-fitting key below; leave facts empty otherwise.\n"
        "intent is 'aside' for everything else - which is one of two different "
        "cases, each needing different handling:\n"
        "  - A genuine question about this project (e.g. 'what am I trying to "
        "achieve with this project?', 'who are the stakeholders?') - answer it "
        "for real using the project facts below, or call search_project_evidence "
        "if the facts below don't cover it. Give a specific, factual answer; "
        "never a deflection and never an empty reply.\n"
        "  - A request to regenerate, redo, or inspect an existing deliverable or "
        "document (e.g. 'redo the requirements doc', 'show me the plan again') - "
        "do not attempt this yourself; reply telling them to use Redraft "
        "requirements for that.\n"
        "reply must never be empty - always produce a real answer for whichever "
        "case applies.\n" + area_guidance + "\n"
        "Call search_project_evidence FIRST, at most once, if answering needs "
        "project memory beyond the facts below. Otherwise answer directly.\n"
        "in_scope: true for anything about this project, or reasonable "
        "general software/product-management questions. Set false ONLY for "
        "clearly unrelated topics (trivia, other companies, off-topic "
        "chit-chat) - then your reply text is discarded, so keep it brief.\n"
        'Return {"reply": str, "in_scope": bool, "intent": "answer"|"aside", '
        '"area": str, "facts": [str]}.\n'
        f"Project facts:\n{digest[:8000]}"
    )
    routed = inference.complete_with_tools(
        model=model,
        messages=[
            {"role": "system", "content": system_base},
            {"role": "user", "content": content},
        ],
        tools=[SEARCH_EVIDENCE_TOOL],
    )
    def _record_new_fact(result: dict) -> str | None:
        if result.get("intent") != "answer" or not result.get("facts"):
            return None
        area = str(result.get("area") or "").strip()
        if area not in area_keys:
            area = "general"
        facts = [str(f) for f in result["facts"] if str(f).strip()]
        if not facts:
            return None
        knowledge.record_facts(area, facts, source_message_id)
        return (
            f"Got it — recorded under {area}: "
            + "; ".join(facts)
            + ". This won't change the accepted documents automatically — use "
            "Reopen Planning or Redraft requirements if you want it reflected there."
        )

    if routed.tool_calls:
        query = str(routed.tool_calls[0].arguments.get("query") or content).strip() or content
        retrieval_result = knowledge.retrieve(query)
        result = complete_json(
            inference,
            model=model,
            system=system_base + "\n" + grounding_rules(augment_context(retrieval_result)),
            user=content,
        )
        reply = _record_new_fact(result)
        if reply is None:
            reply = str(result.get("reply") or "").strip() or POST_COMPLETE_NO_ANSWER_REPLY
            reply = enforce_grounding(
                inference, model=model, text=reply, result=retrieval_result
            ).text
    else:
        result = parse_json_object(routed.content or "") or {}
        reply = _record_new_fact(result)
        if reply is None:
            if result.get("in_scope") is False:
                reply = scope_refusal_reply()
            else:
                # Offered the tool and declined it, but still in-scope -
                # observed live in the interview turn node's identical
                # pattern, that combination produces an ungrounded,
                # deflecting reply with nothing to check it against.
                # Retrieve anyway rather than trust the model's choice not to.
                retrieval_result = knowledge.retrieve(content)
                result = complete_json(
                    inference,
                    model=model,
                    system=system_base
                    + "\n"
                    + grounding_rules(augment_context(retrieval_result)),
                    user=content,
                )
                reply = _record_new_fact(result)
                if reply is None:
                    reply = str(result.get("reply") or "").strip() or POST_COMPLETE_NO_ANSWER_REPLY
                    reply = enforce_grounding(
                        inference, model=model, text=reply, result=retrieval_result
                    ).text
    knowledge.say(reply or POST_COMPLETE_NO_ANSWER_REPLY)


def start_requirements_redraft(session: Session, project: Project, account: Account) -> None:
    """Jump Requirements graph to deliverable picker without re-interview (D83)."""
    if project.phase not in (DONE_PHASE, "requirements"):
        raise ValueError("redraft is only available after Planning is complete")

    # Move off done so the requirements gate thread owns the conversation.
    project.phase = "requirements"
    session.commit()

    template = get_template("requirements")
    graph, config = _graph(session, project, account)
    state = initial_state(template)
    state["coverage"] = {area.key: ANSWERED for area in template.areas}
    # Fresh invoke from START with all areas answered → pick → gate_emit.
    graph.invoke(state, config)
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account.id,
        kind="requirements_redraft_started",
        detail={"phase": "requirements"},
    )


def start_planning_redraft(
    session: Session, project: Project, account: Account, *, area: str | None = None
) -> None:
    """Reopen an already-accepted Planning for a targeted redraft (D89).

    project.phase stays on "requirements"/"done" throughout - planning_redraft_active
    is what makes the Planning tab writable again, not phase. Mirrors
    start_requirements_redraft's fresh-thread jump straight to pick -> gate_emit
    (the acceptance panel reappears), then - since the user's own framing was
    "change this one thing," not "redo all of Planning" - optionally chains one
    more resume into the existing action=="revise" gate branch for a single
    targeted question, reusing _start_gate_revise rather than re-running the
    full interview and re-synthesizing proposals for untouched areas.
    """
    if project.phase not in (DONE_PHASE, "requirements"):
        raise ValueError("Planning can only be reopened after it has been accepted")
    if int(project.planning_doc_version or 0) < 1:
        raise ValueError("Planning has not been accepted yet")

    project.planning_redraft_active = True
    session.commit()

    template = get_template("planning")
    graph, config = _graph(session, project, account, phase_override="planning")
    state = initial_state(template)
    state["coverage"] = {a.key: ANSWERED for a in template.areas}
    graph.invoke(state, config)

    if area:
        graph.invoke(
            Command(
                resume={
                    "action": "revise",
                    "content": f"Revisit {area}.",
                    "area": area,
                    "pack_ids": [],
                    "pack_mode": "separate",
                }
            ),
            config,
        )

    audit_service.record(
        session,
        project_id=project.id,
        account_id=account.id,
        kind="planning_redraft_started",
        detail={"area": area},
    )


def _reask_open_question(
    session: Session,
    project: Project,
    account: Account,
    *,
    knowledge: CardKnowledge,
    phase_override: str | None = None,
) -> None:
    """Re-show the still-open interview question when a turn was diverted
    before ever reaching the graph (blocked by has_pending_intake). Without
    this, a resolved-upload block or a "still reading" notice is the only
    visible message, the actual pending question has usually scrolled out of
    view, and the user has no visible next step even though the interview is
    still correctly waiting on it."""
    if phase_override is None and project.phase == DONE_PHASE:
        return
    graph, config = _graph(session, project, account, phase_override=phase_override)
    state = graph.get_state(config).values or {}
    area_key = state.get("current_area")
    prompts = state.get("last_question_prompts") or []
    if not area_key or not prompts:
        return
    phase_key = phase_override or (project.phase if project.phase != DONE_PHASE else "requirements")
    template = get_template(phase_key)
    area = next((a for a in template.areas if a.key == area_key), None)
    if area is None:
        return
    confirm = bool(state.get("confirm_mode"))
    knowledge.say(
        f"Still waiting on your answer for {area.label}:",
        widget=question_card_widget(
            area=area,
            mode="confirm" if confirm else "ask",
            prompts=prompts,
            raw_options=state.get("last_question_options"),
            known=knowledge.area_facts(area_key) if confirm else None,
        ),
    )


def handle_user_message(
    session: Session,
    project: Project,
    account: Account,
    *,
    content: str,
    skipped: bool = False,
    bound_to_question: bool = False,
    tab: str | None = None,
    skip_redirect_check: bool = False,
) -> None:
    live = assert_tab_writable(project, tab)
    phase = message_phase_for(project, tab=live)
    thread_key = thread_key_for(project, phase=phase)
    message = user_message(
        session, project, content, phase=phase, thread_key=thread_key
    )
    knowledge = CardKnowledge(session, project, phase=phase, thread_key=thread_key)
    phase_override = _phase_override_for_tab(project, live)
    if ingestion_service.has_pending_intake(session, project):
        # Files are still being read (D13 job worker), or one was flagged as
        # off-topic and awaits a keep/discard decision (D86) - answering now
        # would silently miss content or skip past an unresolved decision.
        # Record the message, ask for a resend/decision instead of guessing,
        # matches the existing "between steps" idiom.
        uploads = ingestion_service.list_uploads(session, project)
        reading = [u for u in uploads if u.status in ("queued", "processing")]
        flagged = [u for u in uploads if u.status == "flagged"]
        if flagged and not reading:
            names = ", ".join(u.filename for u in flagged)
            noun = "upload" if len(flagged) == 1 else "uploads"
            knowledge.say(
                f"{len(flagged)} {noun} still need a decision before we continue: "
                f"{names}. Use Keep anyway or Discard on the card above, then send "
                "that again."
            )
        else:
            noun = "file" if len(reading) == 1 else "files"
            preview = content.strip()
            not_processed = (
                f' — your message ("{preview[:120]}") was not processed' if preview else ""
            )
            knowledge.say(
                f"Still reading {len(reading)} uploaded {noun}{not_processed}. "
                "Send it again once processing finishes."
            )
        _reask_open_question(
            session, project, account, knowledge=knowledge, phase_override=phase_override
        )
        return
    if phase_override is None and project.phase == DONE_PHASE:
        handle_post_complete_message(
            session, project, account, content=content, source_message_id=str(message.id)
        )
        return
    ensure_phase_started(session, project, account, phase_override=phase_override)
    graph, config = _graph(session, project, account, phase_override=phase_override)
    snap = graph.get_state(config)
    state = snap.values or {}
    current_area = state.get("current_area")
    if snap.interrupts:
        graph.invoke(
            Command(
                resume={
                    "content": content,
                    "skipped": skipped,
                    "message_id": str(message.id),
                    "bound_to_question": bound_to_question,
                    "skip_redirect_check": skip_redirect_check,
                }
            ),
            config,
        )
    elif snap.next:
        graph.invoke(None, config)
    else:
        knowledge.say(
            "I'm between steps — send another message and I'll continue."
        )
    if current_area:
        audit_service.record(
            session,
            project_id=project.id,
            account_id=account.id,
            kind="area_skipped" if skipped else "area_answered",
            detail={
                "phase": phase_override or project.phase,
                "area": current_area,
                "message_id": str(message.id),
                "snippet": content[:300],
            },
        )
    ensure_phase_started(session, project, account, phase_override=phase_override)


def handle_gate_action(
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
) -> None:
    if action == "redraft":
        if tab not in (None, "", "requirements"):
            raise ValueError("redraft is only available on the Requirements tab")
        start_requirements_redraft(session, project, account)
        return

    if action == "planning_redraft":
        if tab not in (None, "", "planning"):
            raise ValueError("planning_redraft is only available on the Planning tab")
        start_planning_redraft(session, project, account, area=area)
        return

    live = assert_tab_writable(project, tab)
    phase_override = _phase_override_for_tab(project, live)

    if phase_override is None and project.phase == DONE_PHASE:
        return

    ensure_phase_started(session, project, account, phase_override=phase_override)
    graph, config = _graph(session, project, account, phase_override=phase_override)
    graph.invoke(
        Command(
            resume={
                "action": action,
                "content": content,
                "area": area,
                "pack_ids": pack_ids or [],
                "pack_mode": "separate",
            }
        ),
        config,
    )
    ensure_phase_started(session, project, account, phase_override=phase_override)
