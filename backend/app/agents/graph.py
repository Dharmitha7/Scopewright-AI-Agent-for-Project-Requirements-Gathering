"""The phase-runner graph (D45-D47).

One generic graph runs any phase template. Thread = project + phase; the two
pauses are interrupt() calls - waiting for an answer, and the gate itself.

Side-effect rule: a node that calls interrupt() re-executes from its top on
resume, so nodes either write messages OR interrupt as their first statement,
never side-effect-then-interrupt.
https://docs.langchain.com/oss/python/langgraph/interrupts
"""

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.deliverables import packs_for_widget, validate_pack_selection
from app.agents.inference import PURPOSE_TAG, complete_json, facts_by_area, parse_json_object
from app.agents.interview import (
    describes_users_own_request,
    ensure_option_lists,
    guard_premature_enumeration_close,
    is_delegate_answer,
    is_explicit_skip,
    is_unsure_answer,
    selection_mode_for,
)
from app.agents.knowledge import KnowledgePort
from app.agents.readiness import (
    ANSWERED as RD_ANSWERED,
)
from app.agents.readiness import (
    NA as RD_NA,
)
from app.agents.readiness import (
    PENDING as RD_PENDING,
)
from app.agents.readiness import (
    SKIPPED as RD_SKIPPED,
)
from app.agents.readiness import (
    assess_readiness,
    threshold_for,
)
from app.agents.rubrics import area_rubric
from app.agents.skills import interview_skill_ids, skill_text
from app.agents.templates import DONE_PHASE, PLANNING, PhaseTemplate
from app.services import conflict_advice as conflict_advice_service
from app.services.documents import pack_body_failed
from app.services.rag import (
    SEARCH_EVIDENCE_TOOL,
    augment_context,
    enforce_grounding,
    grounding_rules,
    scope_refusal_reply,
)

log = logging.getLogger(__name__)

ANSWERED = RD_ANSWERED
NA = RD_NA
PENDING = RD_PENDING
SKIPPED = RD_SKIPPED
SKIP_LABEL = "Skip for now"


# ponytail: circuit breaker only — not a product follow-up cap; prevents runaway loops.
LOOP_GUARD = 15

# Chip labels that are placeholders, not content — never fabricate a fact
# from these even if the user "picked" one and the model called it aside.
_GENERIC_META_OPTIONS = {"other", "other (specify)", "other (please specify)"}


def question_card_widget(
    *,
    area,
    mode: str,
    prompts: list[str],
    raw_options: object,
    known: list[str] | None = None,
) -> dict:
    """Shape a question_card widget - pure data, no LLM/knowledge dependency,
    so it can be reused outside build_phase_graph() (runner.py re-surfaces a
    still-open question from checkpointed state, without resuming the graph)."""
    options = ensure_option_lists(prompts, raw_options, area_key=area.key)
    return {
        "type": "question_card",
        "purpose": area.key,
        "purpose_label": area.label,
        "purpose_hint": area.hint,
        "mode": mode,
        "prompt": prompts[0] if prompts else "",
        "prompts": prompts,
        "options": options,
        "known": (known or [])[:8] if mode == "confirm" else None,
        "selection_mode": selection_mode_for(area.key, confirm=mode == "confirm"),
    }


def phase_redirect_suggestion_widget(
    *, planning_area: str | None, excerpt: str, reason: str
) -> dict:
    """Shape a phase_redirect_suggestion widget - mirrors off_topic_upload's
    two-action shape (D86): name what was said and why it looks like it
    belongs to a different phase, offer 'Go to Planning' / 'No, keep it
    here' (D89). Pure data, no LLM/knowledge dependency, same reuse pattern
    as question_card_widget."""
    return {
        "type": "phase_redirect_suggestion",
        "planning_area": planning_area,
        "excerpt": excerpt[:280],
        "reason": reason,
    }


class PhaseState(TypedDict, total=False):
    coverage: dict[str, str]  # pending | answered | skipped | na
    current_area: str | None
    goto: str  # conditional-edge signal from the wait/gate nodes
    confirm_mode: bool  # True when the last question was a confirmation
    followups: int  # follow-ups asked for the current area
    last_processed_message_id: str  # prevents re-handling the same resume in one turn
    readiness_score: int
    readiness_threshold: int
    readiness_blocking: list[str]
    readiness_assessed: bool  # True only after assess_readiness at the gate
    revisited_skipped: list[str]
    from_revisit_skip: bool
    defer_resume: bool  # drop stale resume payload when chaining to a new wait
    # Requirements gate (D70): pick packs → generate → review → accept
    gate_stage: str  # "" | pick_packs | review
    selected_packs: list[str]
    pack_mode: str  # combined | separate
    pending_narratives: dict  # {mode, packs, combined}
    draft_teaser: str
    critic_issues: list
    # Gate revise: one targeted question_card — no gate prose + confirm in one turn.
    gate_revise_note: str
    from_gate_revise: bool
    last_question_prompt: str
    last_question_prompts: list[str]
    last_question_options: list[list[str]]


def initial_state(template: PhaseTemplate) -> PhaseState:
    return {
        "coverage": {area.key: PENDING for area in template.areas},
        "current_area": None,
        "goto": "",
        "confirm_mode": False,
        "followups": 0,
        "last_processed_message_id": "",
        "gate_stage": "",
        "selected_packs": [],
        "pack_mode": "",
        "pending_narratives": {},
        "draft_teaser": "",
        "critic_issues": [],
        "gate_revise_note": "",
        "from_gate_revise": False,
        "last_question_prompt": "",
        "last_question_prompts": [],
        "last_question_options": [],
        "readiness_score": 0,
        "readiness_threshold": threshold_for(template.key),
        "readiness_blocking": [],
        "readiness_assessed": False,
        "revisited_skipped": [],
        "from_revisit_skip": False,
        "defer_resume": False,
    }


def build_phase_graph(
    *,
    template: PhaseTemplate,
    knowledge: KnowledgePort,
    inference: Any,
    model: str,
    display_name: str,
    on_accept,
    checkpointer,
    on_gate_research=None,
    on_compose_packs=None,
    on_apply_critic_findings=None,
    list_open_conflicts=None,
    on_resolve_conflict=None,
):
    def _open_conflicts() -> list[dict]:
        if list_open_conflicts is None:
            return []
        return list_open_conflicts()

    def _area(key: str):
        return next(a for a in template.areas if a.key == key)

    def _sys(purpose: str, extra: str = "") -> str:
        # read_back is a one-shot free-text mirror, not a turn in the Q&A
        # loop - the interview skills' "ask one question, use clickable
        # options" guidance doesn't apply here and previously leaked a
        # fabricated, non-interactive pseudo-question into the digest.
        skills = skill_text(*interview_skill_ids(template.key)) if purpose != "read_back" else ""
        skill_block = f"\n\n# Skills\n{skills}" if skills else ""
        return (
            f"{PURPOSE_TAG} {purpose}\n"
            f"You are the {template.label} phase interviewer for a software project. "
            "Never invent facts; what the user did not say is not stated. "
            + extra
            + skill_block
        )

    def _coverage_widget(
        coverage: dict[str, str],
        *,
        readiness_score: int | None = None,
        readiness_threshold: int | None = None,
        readiness_blocking: list[str] | None = None,
    ) -> dict:
        widget: dict[str, Any] = {
            "type": "coverage_meter",
            "phase": template.key,
            "areas": [
                {"key": a.key, "label": a.label, "hint": a.hint, "status": coverage[a.key]}
                for a in template.areas
            ],
        }
        if readiness_score is not None:
            widget["readiness_score"] = readiness_score
        if readiness_threshold is not None:
            widget["readiness_threshold"] = readiness_threshold
        if readiness_blocking:
            widget["readiness_blocking"] = readiness_blocking
        return widget

    def _coverage_widget_for_state(state: PhaseState, coverage: dict[str, str]) -> dict:
        if state.get("readiness_assessed"):
            return _coverage_widget(
                coverage,
                readiness_score=state.get("readiness_score"),
                readiness_threshold=state.get("readiness_threshold") or threshold_for(template.key),
                readiness_blocking=state.get("readiness_blocking"),
            )
        return _coverage_widget(coverage)

    def _coverage_widget_from_state(state: PhaseState, coverage: dict[str, str]) -> dict:
        return _coverage_widget_for_state(state, coverage)

    def _area_key_list() -> str:
        return "\n".join(f"- {a.key}: {a.guidance}" for a in template.areas)

    def _brief() -> str:
        return knowledge.planning_digest()[:400]

    def _synthesize_risks() -> list[str]:
        digest = _fit_digest(knowledge.planning_digest())
        result = complete_json(
            inference,
            model=model,
            system=_sys(
                "risk_synthesis",
                "Analyze this software project and draft 3-6 high-level risks with "
                "brief mitigations. Infer ONLY from the brief, recorded facts, and "
                "retrieved evidence — never invent vendors, metrics, or compliance "
                "regimes unless the context implies them. Each item is one concise "
                'third-person sentence. Return {"risks": [str]}.',
            ),
            user=digest,
        )
        return [str(risk).strip() for risk in (result.get("risks") or []) if str(risk).strip()]

    def _synthesize_proposals(area) -> list[str]:
        if area.key == "risks":
            return _synthesize_risks()
        result = complete_json(
            inference,
            model=model,
            system=_sys(
                "proposal",
                f"Propose 3-5 concrete Planning-level items for '{area.label}' "
                f"from the brief and recorded facts. Never invent vendors or metrics. "
                f"Area: {area.guidance} "
                'Return {"proposals": [str]}.',
            ),
            user=_brief(),
        )
        return [str(item).strip() for item in (result.get("proposals") or []) if str(item).strip()][
            :6
        ]

    def _say_question(
        *,
        area,
        why: str,
        prompts: list[str],
        raw_options: object,
        mode: str,
        known: list[str] | None = None,
    ) -> dict:
        widget = question_card_widget(
            area=area, mode=mode, prompts=prompts, raw_options=raw_options, known=known
        )
        knowledge.say(why, widget=widget)
        return {
            "last_question_prompt": prompts[0] if prompts else "",
            "last_question_prompts": prompts,
            "last_question_options": widget["options"],
        }

    def _reask_open_question(state: PhaseState) -> None:
        """Re-show the still-open question after a turn that didn't answer it
        (aside/process_meta) - without this, later messages (uploads, conflict
        resolutions) push the original question out of view and the user has
        no visible next step, even though the interview is still waiting on it."""
        area_key = state.get("current_area")
        prompts = state.get("last_question_prompts") or []
        if not area_key or not prompts:
            return
        confirm = bool(state.get("confirm_mode"))
        area = _area(area_key)
        _say_question(
            area=area,
            why=f"Still waiting on your answer for {area.label}:",
            prompts=prompts,
            raw_options=state.get("last_question_options"),
            known=knowledge.area_facts(area_key) if confirm else None,
            mode="confirm" if confirm else "ask",
        )

    def _finish_area(
        state: PhaseState,
        area_key: str,
        area_label: str,
        status: str,
        note: str,
    ) -> PhaseState:
        coverage = {**state["coverage"], area_key: status}
        revisited = list(state.get("revisited_skipped") or [])
        extra: dict[str, Any] = {
            "coverage": coverage,
            "current_area": None,
            "goto": "pick",
            "confirm_mode": False,
            "followups": 0,
            "from_revisit_skip": False,
        }
        if state.get("from_revisit_skip") and area_key not in revisited:
            revisited.append(area_key)
            extra["revisited_skipped"] = revisited
        merged = {**state, **extra}
        knowledge.say(note, widget=_coverage_widget_for_state(merged, coverage))
        return {**state, **extra}

    def _close_area(state: PhaseState, area_key: str, area_label: str, note: str) -> PhaseState:
        return _finish_area(state, area_key, area_label, ANSWERED, note)

    def _skip_area(state: PhaseState, area_key: str, area_label: str) -> PhaseState:
        if state.get("from_revisit_skip"):
            return _finish_area(
                state,
                area_key,
                area_label,
                NA,
                f"{area_label}: not specified — we'll note the gap in the draft.",
            )
        return _finish_area(
            state,
            area_key,
            area_label,
            SKIPPED,
            f"{area_label}: skipped for now — we'll revisit before drafting.",
        )

    def _delegate_then_confirm(state: PhaseState, area) -> PhaseState:
        proposals = _synthesize_proposals(area)
        if not proposals:
            knowledge.say(
                f"I need more detail on {area.label} — describe what matters for this project."
            )
            return {**state, "confirm_mode": False, "followups": 0, "goto": "wait"}
        source_id = knowledge.say(
            f"You asked me to decide for {area.label}. Here is a concrete proposal — "
            "confirm it or adjust."
        )
        knowledge.record_facts(area.key, proposals, source_id)
        known = knowledge.area_facts(area.key)
        qstate = _say_question(
            area=area,
            why="Review the proposal and confirm, or tell me what to change.",
            prompts=[f"Does this {area.label} proposal look right?"],
            raw_options=[
                ["Yes, that's correct", "Mostly correct, but I'd add...", "No, let me clarify"]
            ],
            mode="confirm",
            known=known,
        )
        return {
            **state,
            **qstate,
            "confirm_mode": True,
            "followups": 0,
            "goto": "wait",
        }

    def read_back(state: PhaseState) -> PhaseState:
        digest = _fit_digest(knowledge.planning_digest())
        seeded = (
            "The previous phase was accepted; do not re-ask what it established. "
            if template.seeded_from_previous
            else ""
        )
        open_rows = _open_conflicts()
        conflict_guidance = ""
        if open_rows:
            n = len(open_rows)
            conflict_guidance = (
                f"{n} open fact conflict{'s' if n != 1 else ''} will be resolved in the panel "
                "below — summarize only agreed, non-contradictory facts here. Do NOT pose "
                "contradictions as open questions or multiple-choice options in this mirror. "
            )
        mirror = inference.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": _sys(
                        "read_back",
                        seeded
                        + conflict_guidance
                        + "Mirror back what is known with sources, and name what is "
                        "not stated anywhere. Short, plain, no invention. Cite sources in "
                        "plain words from the '(from: ...)' notes (e.g. 'from "
                        "kickoff-notes.md', 'from chat'); never output internal labels, "
                        "brackets like [card:x], or similarity scores.",
                    ),
                },
                {"role": "user", "content": digest},
            ],
        )
        knowledge.say(
            mirror,
            widget=_coverage_widget_for_state(state, state["coverage"]),
        )
        return state

    def _conflict_notice(n: int) -> str:
        return (
            f"{n} conflicting fact{'s' if n != 1 else ''} must be resolved before we "
            "continue. Use Keep A / Keep B below, or ask in chat for a recommendation."
        )

    def _redirect_conflict_wait(state: PhaseState, *, announce: bool) -> PhaseState | None:
        open_rows = _open_conflicts()
        if not open_rows:
            return None
        if announce:
            knowledge.say(_conflict_notice(len(open_rows)))
        return {**state, "goto": "conflict_wait"}

    def pick(state: PhaseState) -> PhaseState:
        blocked = _redirect_conflict_wait(state, announce=True)
        if blocked:
            return blocked
        pending = [a.key for a in template.areas if state["coverage"][a.key] == PENDING]
        return {**state, "current_area": pending[0] if pending else None}

    def _clear_gate_fields(state: PhaseState) -> PhaseState:
        return {
            **state,
            "gate_stage": "",
            "selected_packs": [],
            "pack_mode": "",
            "pending_narratives": {},
            "draft_teaser": "",
            "critic_issues": [],
        }

    def _start_gate_revise(
        state: PhaseState, *, area: str | None, note: str
    ) -> PhaseState:
        """Reopen an area from the gate with one targeted ask — no duplicate gate prose."""
        cleared = _clear_gate_fields(state)
        revise_note = note.strip()
        base = {
            **cleared,
            "gate_revise_note": revise_note,
            "from_gate_revise": True,
        }
        if area and area in state["coverage"]:
            return {
                **base,
                "coverage": {**state["coverage"], area: PENDING},
                "current_area": area,
                "goto": "ask",
            }
        return {**base, "current_area": None, "goto": "wait"}

    def _rubric_block(area) -> str:
        return area_rubric(template.key, area.key, fallback_guidance=area.guidance)

    def ask(state: PhaseState) -> PhaseState:
        blocked = _redirect_conflict_wait(state, announce=True)
        if blocked:
            return blocked
        area = _area(state["current_area"])
        known = knowledge.area_facts(area.key)
        brief = _brief()

        if state.get("from_revisit_skip") and state.get("current_area"):
            area = _area(state["current_area"])
            knowledge.say(
                f"Before we draft, let's revisit **{area.label}** — you skipped it earlier."
            )
            qstate = _say_question(
                area=area,
                why="One quick question so the draft isn't missing this area.",
                prompts=[f"What can you share about {area.label}?"],
                raw_options=None,
                mode="ask",
            )
            return {
                **state,
                **qstate,
                "confirm_mode": False,
                "followups": 0,
                # There is no stale resume to drop here: pick/conflict_check/
                # readiness_check/ask never call interrupt() themselves, so
                # whatever resume triggered this chain was already fully
                # consumed before we got here. Leaving this True made wait()
                # silently swallow the next two real user answers.
                "defer_resume": False,
                "goto": "wait",
            }

        # Propose-then-confirm for thin planning areas (risks, scope, stakeholders).
        if area.key in {"risks", "scope", "stakeholders"} and not known:
            synthesized = _synthesize_proposals(area)
            if synthesized:
                source_id = knowledge.say(
                    f"Based on what you've shared, I've drafted {area.label.lower()} "
                    "for this project. Confirm if they look right, or adjust."
                )
                knowledge.record_facts(area.key, synthesized, source_id)
                known = knowledge.area_facts(area.key)

        if known:
            drafted = complete_json(
                inference,
                model=model,
                system=_sys(
                    "question",
                    f"You are interviewing a stakeholder about: '{brief[:300]}'. "
                    f"The area '{area.label}' already has recorded facts. "
                    "Draft ONE short confirmation question summarizing what we have. "
                    "Always include 3 clickable options. "
                    "Do NOT mark the area done in the question — wait for their answer. "
                    'Return {"prompts": [str], "options": [["Yes, that\'s correct", '
                    '"Mostly correct, but I\'d add...", "No, let me clarify"]], "why": str}.',
                ),
                user=(
                    _rubric_block(area)
                    + "\n\nKnown facts for this area:\n"
                    + "\n".join(f"- {f}" for f in known[:12])
                ),
            )
            prompts = _prompts(drafted) or [
                f"Here is what I have for {area.label} — does this look right?"
            ]
            confirm_opts = [
                ["Yes, that's correct", "Mostly correct, but I'd add...", "No, let me clarify"]
            ]
            qstate = _say_question(
                area=area,
                why=drafted.get("why") or f"Let me confirm what we have for {area.label}.",
                prompts=prompts,
                raw_options=drafted.get("options") or confirm_opts,
                mode="confirm",
                known=known,
            )
            return {**state, **qstate, "confirm_mode": True, "followups": 0}

        drafted = complete_json(
            inference,
            model=model,
            system=_sys(
                "question",
                f"You are interviewing a stakeholder about: '{brief[:300]}'. "
                f"Draft 1 SHORT interview question for '{area.label}'. "
                "Ask about ONE dimension at a time — do not bundle unrelated sub-questions. "
                "If you ask 'which … first' or imply multiple items, you must follow up "
                "before the area can close. "
                "ALWAYS provide 3-6 clickable options plus Other. Never return null options. "
                "Every option must be a concrete, specific candidate answer about THIS "
                "product (grounded in the brief above) — never a meta-instruction about "
                "how to phrase a response (e.g. never 'Combine both into one sentence', "
                "'Provide a brief statement', 'Describe the outcome') and never a generic "
                "app idea unrelated to the brief (e.g. budgeting, task lists, event "
                "discovery, unless the brief is actually about that). If you cannot think "
                "of good on-topic options, offer fewer, narrower ones rather than an "
                "unrelated placeholder — the brief's own subject always wins over a "
                "generic example.\n"
                'Return {"prompts": [str], "options": [[str]], "why": str}. '
                "Do not ask anything the digest already answers.",
            ),
            user=(
                f"{_rubric_block(area)}\n\n"
                f"{augment_context(knowledge.retrieve(f'{area.label}: {area.guidance}'))}\n\n"
                f"Area guidance: {area.guidance}\n\n"
                "Do not ask anything already answered in the retrieved context."
            ),
        )
        prompts = _prompts(drafted) or [area.guidance]
        qstate = _say_question(
            area=area,
            why=drafted.get("why") or f"Let's talk about {area.label}.",
            prompts=prompts,
            raw_options=drafted.get("options"),
            mode="ask",
        )
        return {**state, **qstate, "confirm_mode": False, "followups": 0}

    def wait(state: PhaseState) -> PhaseState:
        blocked = _redirect_conflict_wait(state, announce=True)
        if blocked:
            return blocked
        payload = interrupt({"awaiting": "answer", "area": state["current_area"]})
        source_id = (payload or {}).get("message_id", "")

        if state.get("defer_resume"):
            interrupt({"awaiting": "answer", "area": state["current_area"]})
            return {
                **state,
                "defer_resume": False,
                "last_processed_message_id": source_id
                or state.get("last_processed_message_id", ""),
                "goto": "wait",
            }

        if source_id and source_id == state.get("last_processed_message_id"):
            knowledge.say("Already handled — continue with the question above.")
            interrupt({"awaiting": "answer", "area": state["current_area"]})
            return {**state, "goto": "wait"}

        def _tag(state_out: PhaseState) -> PhaseState:
            if source_id:
                return {**state_out, "last_processed_message_id": source_id}
            return state_out

        area_key = state["current_area"]
        area_label = _area(area_key).label if area_key else "general"
        area_guidance = _area(area_key).guidance if area_key else "anything about the project"
        text = (payload or {}).get("content", "").strip()
        bound_to_question = bool((payload or {}).get("bound_to_question"))
        skip_redirect_check = bool((payload or {}).get("skip_redirect_check"))
        # Chip/card answers are always treated as area answers; free text routes via LLM.
        force_answer = bound_to_question

        explicit_skip = text and is_explicit_skip(text) and not bound_to_question
        if area_key and ((payload or {}).get("skipped") or explicit_skip):
            return _tag(_skip_area(state, area_key, area_label))

        followups = int(state.get("followups") or 0)

        confirm_extra = (
            "The user was asked to CONFIRM recorded facts. Set confirmed=true only for "
            "unqualified yes/correct. If they said 'mostly correct but I'd add' or "
            "'no, let me clarify', area_covered MUST be false and answer_completeness "
            "must be partial or unclear. "
            if state.get("confirm_mode") and area_key
            else ""
        )
        bind_extra = (
            f"CRITICAL: The user's message is very likely answering the current interview "
            f"question about '{area_label}' for the PRODUCT under discussion, even though it "
            f"has no '?' — declarative answers are common. Default to kind 'answer': "
            f"record their choice as a fact for '{area_key}', and reply MUST acknowledge the "
            f"product behavior (e.g. how the app recovers), not say the input was cleared in "
            f"this chat. EXCEPTION: if the message is unmistakably unrelated general "
            f"knowledge/trivia with nothing to do with '{area_label}' or this product (e.g. "
            f"'what is the smallest planet', 'capital of France'), set kind 'aside' and "
            f"in_scope false instead — never invent a fact from trivia text. "
            if force_answer and area_key
            else ""
        )
        purpose = "turn_confirm" if confirm_extra else "turn"
        recorded_now = knowledge.area_facts(area_key) if area_key else []
        fact_context = "Recorded facts for this area:\n" + (
            "\n".join(f"- {f}" for f in recorded_now) if recorded_now else "- none yet"
        )
        last_prompts = state.get("last_question_prompts") or []
        last_options = state.get("last_question_options") or []
        question_context = ""
        if last_prompts:
            question_context = "Last question(s) asked:\n" + "\n".join(
                f"- {p}" for p in last_prompts
            )
        if last_options:
            flat_opts = [opt for group in last_options for opt in (group or []) if opt]
            if flat_opts:
                question_context += "\nOptions shown: " + ", ".join(flat_opts[:12])
        rubric = _rubric_block(_area(area_key)) if area_key else ""

        def _turn_body(evidence_or_tool_note: str) -> str:
            return (
                bind_extra
                + confirm_extra
                + (rubric + "\n\n" if rubric else "")
                + (question_context + "\n\n" if question_context else "")
                + f"The user was asked about '{area_label}' ({area_guidance}). "
                "Handle their message in ONE pass:\n"
                "1. intent: 'answer' (product fact), 'delegate' (ask you to propose), "
                "'process_meta' (instructions about how CrewLane should interview, OR a "
                "request to see/repeat/summarize what has already been recorded (e.g. "
                "'yes, show me the list') — NOT product facts), 'aside' (a question to "
                "you), or 'skip' ONLY when the user explicitly asks to skip/defer this "
                "question (e.g. 'skip for now'). "
                "If the user is unsure ('I don't know'), use intent 'answer' and ask a "
                "narrower follow-up — never skip on uncertainty alone.\n"
                "2. kind: legacy mirror of intent — 'aside' only for evidence/general questions; "
                "otherwise 'answer'. Chip/option text about product behavior is ALWAYS 'answer'.\n"
                "3. facts: only what THEIR WORDS state as PRODUCT facts. Empty for "
                "delegate, process_meta, and aside. Never invent features or metrics, and "
                "never record a fact that narrates the user's own message or request "
                "(e.g. 'user asked to see the list') — that is process_meta, not a fact.\n"
                + _area_key_list()
                + "\n"
                f'Classify each fact under the correct area key — not always "{area_key}".\n'
                f"4. on_topic: true only if their message addresses "
                f"'{area_label}' ({area_guidance}).\n"
                "5. answer_completeness: 'complete' | 'partial' | 'unclear'. "
                "partial when they picked one option but the question had multiple dimensions; "
                "unclear when too vague to record. If the last question used 'first', "
                "'which one', or 'another', area_covered MUST be false unless the user "
                "explicitly confirms that is everything or describes another item. "
                "area_covered MUST be false unless "
                "answer_completeness is complete AND the rubric essentials are met.\n"
                f"6. area_covered: true only when rubric essentials for '{area_label}' "
                "are satisfied AND answer_completeness is complete. "
                "Do NOT close because metrics or nice-to-haves are missing. "
                "Do NOT close on a single thin chip if the rubric needs more. "
                "area_covered MUST be false when on_topic is false.\n"
                "7. gaps: if not covered, max 3 missing pieces from the rubric.\n"
                "8. reply: 1-2 sentences acknowledging what you captured.\n"
                "9. If area_covered is false: followup_prompt (one short question) and "
                "followup_options (3-6 clickable strings). When on_topic is false, "
                "followup_prompt returns to the original question.\n"
                'Return {"intent": "answer"|"delegate"|"process_meta"|"aside"|"skip", '
                '"kind": "answer"|"aside", "in_scope": bool, "on_topic": bool, '
                '"answer_completeness": "complete"|"partial"|"unclear", '
                '"confirmed": bool, "facts": [{"text": str, "area": str}], '
                '"area_covered": bool, "gaps": [str], "reply": str, '
                '"followup_prompt": str, "followup_options": [str]}.\n'
                + fact_context
                + evidence_or_tool_note
            )

        # D81: decide-and-answer via one bounded, optional tool call instead
        # of a separate decide_retrieval() routing call plus a generate call.
        # If the model answers directly, that is the whole turn in one call
        # (down from two). If it reaches for evidence, the follow-up call
        # below offers no tools at all - "at most one retrieval, once" is
        # enforced structurally, not by trusting the model to stop.
        retrieval_result = None
        retrieval_query = ""
        retrieval_reason = "message_is_bound_to_interview_answer"
        if force_answer:
            # Matches decide_retrieval(force_answer=True)'s old short-circuit:
            # a message bound to the current interview question never needs
            # project evidence, so no model call even offers the tool.
            result = complete_json(
                inference,
                model=model,
                system=_sys(purpose, _turn_body("\n9. " + grounding_rules(""))),
                user=text,
            )
        else:
            routed = None
            try:
                routed = inference.complete_with_tools(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": _sys(
                                purpose,
                                _turn_body(
                                    "\n9. Call search_project_evidence FIRST, at most once, if "
                                    "answering needs project memory - prior decisions, "
                                    "requirements, people, dates, identifiers, uploaded evidence, "
                                    "or a claim to verify. Otherwise answer directly with the "
                                    "schema above; never call it for greetings or new answers.\n"
                                    "10. in_scope: true for anything about this project, or "
                                    "reasonable general software/product-management questions. "
                                    "Set false ONLY for clearly unrelated topics (trivia, other "
                                    "companies, off-topic chit-chat) - then use intent 'aside' "
                                    "and do not call the tool; your reply text is discarded in "
                                    "that case, so keep it brief."
                                ),
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                    tools=[SEARCH_EVIDENCE_TOOL],
                )
            except Exception:
                # Observed live: some models (gpt-oss via Groq) occasionally emit a
                # non-declared "commentary" pseudo tool-call the provider rejects
                # with a 400. Retry once with no tools offered at all - same
                # short-circuit force_answer already uses. complete_json() never
                # raises (fails soft to {}, see its docstring), so this recovers
                # even if the underlying provider call fails again.
                log.warning(
                    "complete_with_tools failed in wait() for area %s, retrying without tools",
                    area_key, exc_info=True,
                )
                result = complete_json(
                    inference,
                    model=model,
                    system=_sys(purpose, _turn_body("\n9. " + grounding_rules(""))),
                    user=text,
                )
                retrieval_reason = "tool_call_failed_retried_without_tools"
            if routed is not None and routed.tool_calls:
                call = routed.tool_calls[0]  # tool_choice="auto" (not parallel): at most one
                retrieval_query = str(call.arguments.get("query") or text).strip() or text
                retrieval_reason = "tool_call"
                retrieval_result = knowledge.retrieve(retrieval_query)
                retrieved_context = augment_context(retrieval_result)
                result = complete_json(
                    inference,
                    model=model,
                    system=_sys(purpose, _turn_body("\n9. " + grounding_rules(retrieved_context))),
                    user=text,
                )
                # Scope was already decided at the routing call above (D81):
                # calling the tool at all IS the model's in-scope assertion.
                # This follow-up call's prompt carries no scope guidance, so
                # a re-guessed in_scope here is unreliable - observed live,
                # empty retrieved evidence made the model set it false,
                # conflating "no evidence found" with "off-topic" and
                # wrongly refusing an on-topic question with no evidence yet.
                result["in_scope"] = True
            elif routed is not None:
                retrieval_reason = "no_tool_call_direct_answer"
                result = parse_json_object(routed.content or "") or {}
                is_aside = result.get("intent") == "aside" or result.get("kind") == "aside"
                if is_aside and result.get("in_scope") is not False:
                    # Offered the tool and declined it, but still an in-scope
                    # aside - observed live, that combination produces an
                    # ungrounded, deflecting reply with nothing to check it
                    # against (enforce_grounding needs a retrieval_result to
                    # run at all). Retrieve anyway rather than trust the
                    # model's choice not to; costs one more call, only for
                    # this narrow, already-rare combination.
                    retrieval_reason = "tool_declined_retrieved_anyway"
                    retrieval_query = text
                    retrieval_result = knowledge.retrieve(retrieval_query)
                    retrieved_context = augment_context(retrieval_result)
                    body = _turn_body("\n9. " + grounding_rules(retrieved_context))
                    result = complete_json(
                        inference, model=model, system=_sys(purpose, body), user=text
                    )
                    result["in_scope"] = True

        knowledge.trace_retrieval_decision(
            {
                "should_retrieve": retrieval_result is not None,
                "query": retrieval_query,
                "reason": retrieval_reason,
                "area": area_key,
                "message_id": source_id,
                "in_scope": result.get("in_scope", True),
                "on_topic": result.get("on_topic", True),
            }
        )

        # Enforced in code, not just prompted for: observed live, the model
        # would still mark area_covered true off an off-topic message despite
        # explicit prompt instructions not to. on_topic is a narrower,
        # harder-to-fudge question ("does THIS message address what was
        # asked") than area_covered ("is the area done"), and this is the
        # actual gate - the model's own area_covered is not trusted alone.
        if result.get("on_topic") is False:
            result["area_covered"] = False

        # Enforced in code, not just prompted for: observed live, "yes, show
        # me the list" (a meta-request to see already-recorded content) got
        # classified as intent 'answer' with a fabricated fact narrating the
        # request itself ("User requested to see the MVP scope list") instead
        # of intent 'process_meta' with no facts, despite the prompt telling
        # it facts must be product statements. Drop any such fact here rather
        # than trust the model's own intent/facts split alone.
        raw_facts = result.get("facts")
        if isinstance(raw_facts, list):
            result["facts"] = [
                f
                for f in raw_facts
                if not (
                    isinstance(f, dict)
                    and describes_users_own_request(str(f.get("text") or ""))
                )
            ]

        completeness = str(result.get("answer_completeness") or "unclear").strip().lower()
        if completeness != "complete":
            result["area_covered"] = False

        guarded_covered, enum_prompt, enum_opts = guard_premature_enumeration_close(
            last_prompts=last_prompts,
            answer_text=text,
            area_label=area_label,
            area_covered=bool(result.get("area_covered")),
        )
        if result.get("area_covered") and not guarded_covered:
            result["area_covered"] = False
            result["answer_completeness"] = "partial"
            result["followup_prompt"] = enum_prompt
            result["followup_options"] = enum_opts

        # force_answer nudges the model to prefer 'answer' (D62a: declaratives are
        # answers). But when the model still says aside AND explicitly flags
        # in_scope=false, that's the trivia exception above firing on purpose -
        # trust it rather than fabricating a fact from unrelated text.
        if force_answer and result.get("kind") == "aside" and result.get("in_scope") is not False:
            result["kind"] = "answer"
            result["intent"] = "answer"
            if not result.get("facts") and text:
                result["facts"] = [{"text": text, "area": area_key or "general"}]
            reply_now = str(result.get("reply") or "")
            if (
                not reply_now
                or "cleared" in reply_now.lower()
                or "provide next" in reply_now.lower()
            ):
                result["reply"] = f"Got it for {area_label} — recorded: {text[:240]}" + (
                    "…" if len(text) > 240 else ""
                )
        elif (
            force_answer
            and result.get("kind") == "aside"
            and result.get("in_scope") is False
            and text
            and text.strip().lower() not in _GENERIC_META_OPTIONS
            and not is_delegate_answer(text)
            and not is_explicit_skip(text)
            and not is_unsure_answer(text)
            and any(
                text.strip().lower() == opt.strip().lower()
                for group in last_options
                for opt in (group or [])
                if opt
            )
        ):
            # The user picked one of the exact chip options this same turn
            # offered - that can never be off-topic trivia, whatever the
            # model's own in_scope guess said. Delegate/skip/unsure phrases
            # ("You decide for me", "Skip for now", "Not sure") and generic
            # placeholder labels ("Other", "Other (specify)") are excluded
            # above so this never fabricates a literal fact out of a
            # meta-option - only a genuine content choice gets recorded here.
            result["kind"] = "answer"
            result["intent"] = "answer"
            result["in_scope"] = True
            if not result.get("facts"):
                result["facts"] = [{"text": text, "area": area_key or "general"}]
            result["reply"] = f"Got it for {area_label} — recorded: {text[:240]}" + (
                "…" if len(text) > 240 else ""
            )

        intent = str(result.get("intent") or result.get("kind") or "answer").strip().lower()
        def _try_planning_redirect() -> bool:
            """True (and already emitted the widget + re-shown the question)
            if the raw message looks like a Planning-level statement. Shared
            by both paths that can reach it - a normal answer the model
            marked on_topic=false (has facts to redirect) and an aside the
            model marked fully out of scope. Found live (D90): "the hospital
            board wants final sign-off, not just clinic administration" - a
            genuine stakeholder change - got classified aside/in_scope=false
            (fully unrelated, not just off-topic-for-this-question), so the
            on_topic-only gate below never saw it at all. A stakeholder/
            scope/risk change is a different phase, not off-topic chit-chat."""
            if template.key != "requirements" or skip_redirect_check:
                return False
            redirect = complete_json(
                inference,
                model=model,
                system=_sys(
                    "planning_redirect_check",
                    "The user's message may describe a PLANNING-level change (the "
                    "overall business need, v1 scope/exclusions, stakeholders, or a "
                    "top-level risk) rather than a Requirements-level detail for the "
                    "already-agreed scope. Planning areas:\n"
                    + "\n".join(f"- {a.key}: {a.guidance}" for a in PLANNING.areas)
                    + '\nReturn {"belongs_to_planning": bool, "planning_area": str, '
                    '"reason": str}. planning_area must be one of the keys above, or '
                    'empty string if belongs_to_planning is false.',
                ),
                user=text,
            )
            if not redirect.get("belongs_to_planning"):
                return False
            planning_area = str(redirect.get("planning_area") or "").strip() or None
            if planning_area not in {a.key for a in PLANNING.areas}:
                planning_area = None
            knowledge.say(
                str(redirect.get("reason") or "This sounds like a Planning-level change."),
                widget=phase_redirect_suggestion_widget(
                    planning_area=planning_area,
                    excerpt=text,
                    reason=str(redirect.get("reason") or ""),
                ),
            )
            _reask_open_question(state)
            return True

        if intent == "aside" or result.get("kind") == "aside":
            if result.get("in_scope") is False:
                if _try_planning_redirect():
                    return _tag({**state, "goto": "wait"})
                reply = scope_refusal_reply(area_label=area_label if area_key else None)
            else:
                reply = str(result.get("reply") or "That is not stated anywhere yet.")
                if retrieval_result:
                    reply = enforce_grounding(
                        inference, model=model, text=reply, result=retrieval_result
                    ).text
            knowledge.say(reply)
            _reask_open_question(state)
            return _tag({**state, "goto": "wait"})

        if intent == "process_meta":
            knowledge.say(
                str(result.get("reply") or "Got it — I'll adjust how I ask. What else?")
            )
            _reask_open_question(state)
            return _tag({**state, "goto": "wait"})

        if intent == "delegate" and area_key:
            return _tag(_delegate_then_confirm(state, _area(area_key)))

        if intent == "skip" and area_key:
            return _tag(_skip_area(state, area_key, area_label))

        if result.get("on_topic") is False and result.get("facts"):
            # Observed live: an off-topic message's facts kept landing under
            # area_key anyway despite the "classify under its real area"
            # instruction in _turn_body - the same prompt-only reliability
            # gap on_topic itself hit. Only spend the extra call when
            # on_topic already flagged a real mismatch (most turns are
            # on-topic and skip this entirely) - a narrow, dedicated
            # reclassify question, not a bigger extraction prompt.
            original_facts = [f for f in result["facts"] if isinstance(f, dict)]
            texts = [str(f.get("text") or "") for f in original_facts]
            reclassified = complete_json(
                inference,
                model=model,
                system=_sys(
                    "reclassify_facts",
                    "This message was about a different area than what was asked, so "
                    "these already-extracted facts may be filed under the wrong area. "
                    "Reclassify each into the coverage area key it actually belongs "
                    "to, same order, same count.\n" + _area_key_list() + "\n"
                    'Return {"areas": [str]}.',
                ),
                user="\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts)),
            )
            areas = reclassified.get("areas") or []
            if len(areas) == len(original_facts):
                result["facts"] = [
                    {**f, "area": areas[i]} for i, f in enumerate(original_facts)
                ]

        # Cross-phase redirect (D89/D90): see _try_planning_redirect() above
        # for why this is a separate, narrow call rather than folded into the
        # schema above. Gated on the same rare "on_topic=false, has facts"
        # branch the reclassify above already pays for - not a new always-on
        # call.
        if result.get("on_topic") is False and result.get("facts") and _try_planning_redirect():
            return _tag({**state, "goto": "wait"})

        by_area = facts_by_area(
            result,
            default_area=area_key or "general",
            valid_areas={a.key for a in template.areas},
        )
        recorded: list[str] = []
        for fact_area, facts in by_area.items():
            knowledge.record_facts(fact_area, facts, source_id)
            recorded.extend(facts)

        reply = result.get("reply") or (
            f"Recorded {len(recorded)} fact(s) for {area_label}." if recorded else "Noted."
        )
        knowledge.say(
            reply,
            widget=(
                {
                    "type": "fact_log",
                    "area": area_key or "general",
                    "facts": recorded,
                    "source_message_id": source_id,
                }
                if recorded
                else None
            ),
        )
        if _open_conflicts():
            knowledge.say(
                "New conflicting facts were recorded — resolve them before we continue."
            )
            return _tag({**state, "goto": "conflict_wait"})

        if area_key is None:
            return _tag({**state, "goto": "pick", "confirm_mode": False})

        followups = int(state.get("followups") or 0)
        if followups >= LOOP_GUARD:
            knowledge.say(
                f"We've tried several times on {area_label}. "
                "Use **Skip for now** if you want to defer — we'll revisit before drafting."
            )
            return _tag({**state, "goto": "wait"})

        if result.get("area_covered"):
            return _tag(_close_area(state, area_key, area_label, f"{area_label}: covered."))

        area = _area(area_key)
        follow_prompt = str(result.get("followup_prompt") or "").strip()
        if not follow_prompt:
            gaps = [str(g).strip() for g in (result.get("gaps") or []) if str(g).strip()]
            follow_prompt = gaps[0] if gaps else f"What else should we capture for {area_label}?"
        raw_opts = result.get("followup_options")
        if isinstance(raw_opts, list) and raw_opts and isinstance(raw_opts[0], str):
            follow_options: object = [raw_opts]
        else:
            follow_options = raw_opts
        qstate = _say_question(
            area=area,
            # `result["reply"]` was already shown above as the fact-recording
            # acknowledgment (line ~952) - reusing it here duplicated the same
            # sentence back-to-back in the chat transcript.
            why="Let's continue.",
            prompts=[follow_prompt],
            raw_options=follow_options,
            mode="ask",
        )
        return _tag(
            {
                **state,
                **qstate,
                "goto": "wait",
                "confirm_mode": False,
                "followups": followups + 1,
            }
        )

    def _critic_issues(text: str) -> list[dict]:
        review = complete_json(
            inference,
            model=model,
            system=_sys(
                "critic",
                f"You are the senior reviewer for this draft {template.document}. "
                "Find the problems a good reviewer would flag before sign-off:\n"
                "- ambiguous wording that two readers would interpret differently\n"
                "- statements that cannot be verified or tested as written\n"
                "- internal contradictions in the draft\n"
                "- areas whose content is too thin to build from\n"
                "Judge ONLY what is written below - do not invent requirements the "
                "project should have. At most 6 issues; an empty list is a valid "
                "answer for a clean draft. "
                'Return {"issues": [{"severity": "high"|"medium"|"low", '
                '"area": str, "note": str}]}.',
            ),
            user=text,
        )
        return [
            {
                "severity": str(i.get("severity", "medium")),
                "area": str(i.get("area", "")),
                "note": str(i.get("note", "")).strip(),
            }
            for i in (review.get("issues") or [])
            if str(i.get("note", "")).strip()
        ][:6]

    def _facts_by_area() -> dict[str, list[str]]:
        return {a.key: knowledge.area_facts(a.key) for a in template.areas}

    def readiness_check(state: PhaseState) -> PhaseState:
        blocked = _redirect_conflict_wait(state, announce=False)
        if blocked:
            return blocked

        revisited = list(state.get("revisited_skipped") or [])
        skipped = [
            a.key
            for a in template.areas
            if state["coverage"].get(a.key) == SKIPPED and a.key not in revisited
        ]
        if skipped:
            area_key = skipped[0]
            return {
                **state,
                "current_area": area_key,
                "from_revisit_skip": True,
                "defer_resume": True,
                "confirm_mode": False,
                "followups": 0,
                "goto": "ask",
            }

        assessment = assess_readiness(
            inference=inference,
            model=model,
            template=template,
            digest=_fit_digest(knowledge.planning_digest()),
            coverage=state["coverage"],
            facts_by_area=_facts_by_area(),
        )
        threshold = threshold_for(template.key)
        base = {
            **state,
            "readiness_score": assessment.overall_score,
            "readiness_threshold": threshold,
            "readiness_blocking": assessment.blocking_areas,
            "readiness_assessed": True,
        }
        widget = _coverage_widget(
            state["coverage"],
            readiness_score=assessment.overall_score,
            readiness_threshold=threshold,
            readiness_blocking=assessment.blocking_areas,
        )

        if not assessment.can_draft:
            pending_skipped = [
                k
                for k in assessment.blocking_areas
                if state["coverage"].get(k) == SKIPPED and k not in revisited
            ]
            if pending_skipped:
                area_key = pending_skipped[0]
                return {
                    **base,
                    "current_area": area_key,
                    "from_revisit_skip": True,
                    "defer_resume": True,
                    "confirm_mode": False,
                    "followups": 0,
                    "goto": "ask",
                }
            thin = ", ".join(a.replace("_", " ") for a in assessment.blocking_areas[:3])
            knowledge.say(
                f"Draft readiness is **{assessment.overall_score}%** (need {threshold}%). "
                + (f"Still thin: {thin}." if thin else assessment.summary or "Need more detail."),
                widget=widget,
            )
            coverage = dict(state["coverage"])
            reopened = False
            for key in assessment.blocking_areas[:2]:
                if coverage.get(key) in (ANSWERED, SKIPPED):
                    coverage[key] = PENDING
                    reopened = True
            if reopened:
                return {**base, "coverage": coverage, "goto": "pick"}
            # Nothing identified to send the user back to: looping straight
            # to "pick" here re-enters readiness_check in the same tick with
            # no new input, calling assess_readiness again on identical
            # data - a second, independent LLM judgment that can (and did)
            # disagree with the first, showing two contradictory readiness
            # percentages back to back with no user action in between. Wait
            # for a real turn instead (same no-area pattern used elsewhere,
            # e.g. line 441) so the next assessment only runs after the user
            # actually adds something - this does not loosen the gate itself.
            return {**base, "current_area": None, "goto": "wait"}

        knowledge.say(
            f"Draft readiness **{assessment.overall_score}%** — enough to generate "
            f"the {template.document}.",
            widget=widget,
        )
        return {**base, "goto": "gate_emit"}

    def gate_emit(state: PhaseState) -> PhaseState:
        blocked = _redirect_conflict_wait(state, announce=True)
        if blocked:
            return blocked

        if on_gate_research is not None:
            on_gate_research()

        # Requirements: mandatory pack picker before any document LLM (D70 / option C).
        if template.key == "requirements":
            knowledge.say(
                f"Every {template.label} area is covered. Choose which deliverables "
                "to generate — this is required before accept.",
                widget={
                    "type": "deliverable_picker",
                    "phase": template.key,
                    "document": template.document,
                    "packs": packs_for_widget(),
                    "coverage": state["coverage"],
                },
            )
            return {
                **state,
                "gate_stage": "pick_packs",
                "selected_packs": [],
                "pack_mode": "",
                "pending_narratives": {},
                "draft_teaser": "",
                "critic_issues": [],
            }

        digest = knowledge.planning_digest()
        llm_digest = _fit_digest(digest)
        preview = inference.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{PURPOSE_TAG} narrative\n"
                        f"You write a draft {template.document} for a software project. "
                        "Compose a professional, readable document STRICTLY from the facts "
                        "below. STRICT RULE: never add numbers, percentages, metrics, "
                        "vendors, standards, or requirements the facts do not state - a "
                        "gap stays a gap. Use markdown with # / ## headings, paragraphs, "
                        "and - bullet lists. Start with a one-paragraph executive summary. "
                        "Then one section per area with clear headings."
                    ),
                },
                {"role": "user", "content": llm_digest},
            ],
        )
        issues: list[dict] = []
        knowledge.say(
            f"The {template.document} draft is ready — review it and accept, "
            "or send an area back for revision.",
            widget={
                "type": "acceptance_panel",
                "phase": template.key,
                "document": template.document,
                "coverage": state["coverage"],
                "digest": preview.strip() or digest,
                "full_digest": preview.strip() or digest,
                "issues": issues,
            },
        )
        return {**state, "gate_stage": "review", "critic_issues": issues, "draft_teaser": preview}

    def _gate_free_text(state: PhaseState, text: str) -> PhaseState:
        gate_stage = state.get("gate_stage") or ""
        teaser = str(state.get("draft_teaser") or "")
        digest = _fit_digest(knowledge.planning_digest())
        preview = teaser.strip() or digest[:4000]
        areas = ", ".join(a.key for a in template.areas)

        result = complete_json(
            inference,
            model=model,
            system=_sys(
                "gate_turn",
                f"User is at the {template.label} gate (stage: {gate_stage}). "
                "Classify their free-text message:\n"
                "- qa: question about the draft, deliverables, or coverage\n"
                "- revise: wants to revisit an interview area and change facts\n"
                "- accept: clearly accepts the draft/gate (e.g. 'looks good, ship it')\n"
                "- ack: general comment, not actionable\n"
                f"Valid area keys: {areas}.\n"
                "For revise, reply MUST be a brief acknowledgement only — no questions; "
                "the interview asks next.\n"
                'Return {"intent": "qa"|"revise"|"accept"|"ack", "reply": str, "area": str|null}.',
            ),
            user=f"Draft preview:\n{preview[:4000]}\n\nUser: {text}",
        )

        intent = str(result.get("intent") or "ack").strip().lower()
        reply = str(result.get("reply") or "").strip()

        if intent == "revise":
            area = str(result.get("area") or "").strip() or None
            return _start_gate_revise(state, area=area, note=text)

        if intent == "accept" and gate_stage == "review":
            if template.key == "requirements":
                pending = state.get("pending_narratives") or {}
                if not pending.get("packs"):
                    knowledge.say("Select deliverables and generate them before accepting.")
                    return {**state, "goto": "gate_wait"}
                failed = [
                    k for k, body in (pending.get("packs") or {}).items() if pack_body_failed(body)
                ] or list(pending.get("failed_packs") or [])
                if failed:
                    knowledge.say(
                        "Cannot accept while generation failed for: "
                        + ", ".join(str(k) for k in failed)
                        + ". Re-run Generate selected, then Accept."
                    )
                    return {**state, "goto": "gate_wait"}
                on_accept(pending)
            else:
                on_accept(None)
            next_msg = (
                f"Next phase: {template.next_phase}."
                if template.next_phase
                else (
                    "You can keep chatting about the project, or use "
                    "Redraft requirements to regenerate deliverables."
                )
            )
            knowledge.say(
                f"{template.document} accepted by {display_name}. {next_msg}",
                widget={
                    "type": "gate_accepted",
                    "phase": template.key,
                    "accepted_by": display_name,
                },
            )
            return {**state, "goto": "end"}

        knowledge.say(
            reply or "Noted. Ask me about the draft, or use the gate card to continue."
        )
        return {**state, "goto": "gate_wait"}

    def conflict_check(state: PhaseState) -> PhaseState:
        open_rows = _open_conflicts()
        if not open_rows:
            return state
        knowledge.say(_conflict_notice(len(open_rows)))
        return {**state, "goto": "conflict_wait"}

    def _apply_conflict_pick(row: dict, pick: str) -> None:
        if on_resolve_conflict is None:
            return
        winner = row["card_a"]["id"] if pick == "a" else row["card_b"]["id"]
        on_resolve_conflict(str(row["id"]), winner)

    def conflict_wait(state: PhaseState) -> PhaseState:
        payload = interrupt({"awaiting": "conflicts", "phase": template.key})

        if not _open_conflicts():
            knowledge.say("All conflicts resolved — continuing.")
            pending = [a.key for a in template.areas if state["coverage"][a.key] == PENDING]
            if pending:
                return {**state, "goto": "pick"}
            if state.get("current_area"):
                return {**state, "goto": "wait"}
            return {**state, "goto": ""}

        open_rows = _open_conflicts()
        current = open_rows[0]
        text = str((payload or {}).get("content") or "").strip()

        if text and is_delegate_answer(text) and on_resolve_conflict is not None:
            advice = conflict_advice_service.advise_single_conflict(
                inference, model=model, row=current, user_message=text
            )
            pick = str(advice.get("pick") or "").strip().lower()
            if pick in {"a", "b"}:
                _apply_conflict_pick(current, pick)
                why = str(advice.get("why") or "").strip()
                tail = f": {why}" if why else ""
                knowledge.say(
                    f"Kept **{pick.upper()}** for this conflict{tail}. "
                    + (
                        "Next one is ready below."
                        if _open_conflicts()
                        else "All conflicts resolved — continuing."
                    )
                )
                return {**state, "goto": "conflict_wait"}

        if text:
            advice = conflict_advice_service.advise_single_conflict(
                inference, model=model, row=current, user_message=text
            )
            knowledge.say(conflict_advice_service.format_advice_message(advice))

        return {**state, "goto": "conflict_wait"}

    def gate_wait(state: PhaseState) -> PhaseState:
        payload = interrupt({"awaiting": "gate", "phase": template.key})
        action = (payload or {}).get("action")

        if action == "select_packs":
            if template.key != "requirements" or on_compose_packs is None:
                knowledge.say("Deliverable selection is only available in Requirements.")
                return {**state, "goto": "gate_wait"}
            try:
                keys = validate_pack_selection(list((payload or {}).get("pack_ids") or []))
                # D84: separate documents only.
                mode = "separate"
            except ValueError as exc:
                knowledge.say(f"Could not generate deliverables: {exc}")
                return {**state, "goto": "gate_wait"}

            composed = on_compose_packs(keys, mode)
            preview = str(composed.get("display") or composed.get("teaser") or "")
            issues = _critic_issues(_fit_digest(preview)) if preview.strip() else []
            if on_apply_critic_findings is not None:
                composed = on_apply_critic_findings(composed, issues)
            teaser = str(composed.get("teaser") or "")
            full = str(composed.get("display") or teaser)
            failed_packs = [str(k) for k in (composed.get("failed_packs") or []) if k]
            if failed_packs:
                labels = ", ".join(failed_packs)
                summary = (
                    f"Generated {len(keys)} deliverable(s) as separate documents, but generation "
                    f"failed for: {labels}. Re-run Generate selected before Accept — "
                    "do not freeze a broken pack."
                )
            else:
                summary = (
                    f"Generated {len(keys)} separate deliverable(s). Review the preview, "
                    "open Read full draft to see everything, then accept or revise."
                )
            knowledge.say(
                summary,
                widget={
                    "type": "acceptance_panel",
                    "phase": template.key,
                    "document": template.document,
                    "coverage": state["coverage"],
                    "digest": teaser,
                    "full_digest": full,
                    "issues": issues,
                    "selected_packs": keys,
                    "pack_mode": mode,
                    "failed_packs": failed_packs,
                },
            )
            return {
                **state,
                "gate_stage": "review",
                "selected_packs": keys,
                "pack_mode": mode,
                "pending_narratives": {
                    "mode": composed["mode"],
                    "packs": composed["packs"],
                    "combined": composed.get("combined"),
                    "failed_packs": failed_packs,
                },
                "draft_teaser": teaser,
                "critic_issues": issues,
                "goto": "gate_wait",
            }

        if action == "accept":
            if template.key == "requirements":
                pending = state.get("pending_narratives") or {}
                if not pending.get("packs"):
                    knowledge.say("Select deliverables and generate them before accepting.")
                    return {**state, "goto": "gate_wait"}
                failed = [
                    k for k, body in (pending.get("packs") or {}).items() if pack_body_failed(body)
                ] or list(pending.get("failed_packs") or [])
                if failed:
                    knowledge.say(
                        "Cannot accept while generation failed for: "
                        + ", ".join(str(k) for k in failed)
                        + ". Re-run Generate selected, then Accept."
                    )
                    return {**state, "goto": "gate_wait"}
                on_accept(pending)
            else:
                on_accept(None)
            next_msg = (
                f"Next phase: {template.next_phase}."
                if template.next_phase
                else (
                    "You can keep chatting about the project, or use "
                    "Redraft requirements to regenerate deliverables."
                )
            )
            knowledge.say(
                f"{template.document} accepted by {display_name}. {next_msg}",
                widget={
                    "type": "gate_accepted",
                    "phase": template.key,
                    "accepted_by": display_name,
                },
            )
            return {**state, "goto": "end"}

        if action == "revise":
            note = str((payload or {}).get("content") or "").strip()
            area = str((payload or {}).get("area") or "").strip() or None
            return _start_gate_revise(state, area=area, note=note)

        # Free-text while the gate is open: Q&A, natural-language revise/accept.
        note = str((payload or {}).get("content") or "").strip()
        if note:
            return _gate_free_text(state, note)
        return {**state, "goto": "gate_wait"}

    builder = StateGraph(PhaseState)
    builder.add_node("read_back", read_back)
    builder.add_node("pick", pick)
    builder.add_node("ask", ask)
    builder.add_node("wait", wait)
    builder.add_node("conflict_check", conflict_check)
    builder.add_node("conflict_wait", conflict_wait)
    builder.add_node("readiness_check", readiness_check)
    builder.add_node("gate_emit", gate_emit)
    builder.add_node("gate_wait", gate_wait)

    def _route_pick(s: PhaseState) -> str:
        if s.get("goto") == "conflict_wait":
            return "conflict_wait"
        return "ask" if s.get("current_area") else "conflict_check"

    def _route_ask(s: PhaseState) -> str:
        return "conflict_wait" if s.get("goto") == "conflict_wait" else "wait"

    def _route_wait(s: PhaseState) -> str:
        g = s.get("goto") or "pick"
        if g in {"wait", "pick", "conflict_wait"}:
            return g
        return "pick"

    def _route_readiness(s: PhaseState) -> str:
        g = s.get("goto") or "gate_emit"
        if g in {"pick", "ask", "gate_emit"}:
            return g
        return "gate_emit"

    def _route_conflict_wait(s: PhaseState) -> str:
        g = s.get("goto")
        if g == "conflict_wait":
            return "conflict_wait"
        if g == "pick":
            return "pick"
        if g == "wait":
            return "wait"
        return "readiness_check"

    builder.add_edge(START, "read_back")
    builder.add_edge("read_back", "pick")
    builder.add_conditional_edges("pick", _route_pick, ["ask", "conflict_check", "conflict_wait"])
    builder.add_conditional_edges("ask", _route_ask, ["wait", "conflict_wait"])
    builder.add_conditional_edges("wait", _route_wait, ["wait", "pick", "conflict_wait"])
    builder.add_conditional_edges(
        "conflict_check",
        lambda s: "conflict_wait" if s.get("goto") == "conflict_wait" else "readiness_check",
        ["conflict_wait", "readiness_check"],
    )
    builder.add_conditional_edges(
        "conflict_wait",
        _route_conflict_wait,
        ["conflict_wait", "pick", "wait", "readiness_check"],
    )
    builder.add_conditional_edges(
        "readiness_check",
        _route_readiness,
        ["pick", "ask", "gate_emit"],
    )
    builder.add_conditional_edges(
        "gate_emit",
        lambda s: "conflict_wait" if s.get("goto") == "conflict_wait" else "gate_wait",
        ["conflict_wait", "gate_wait"],
    )
    builder.add_conditional_edges(
        "gate_wait",
        lambda s: END if s.get("goto") == "end" else s.get("goto") or "pick",
        ["wait", "pick", "ask", "gate_wait", END],
    )
    return builder.compile(checkpointer=checkpointer)


def _prompts(drafted: dict) -> list[str]:
    """1-3 question prompts from a draft; tolerates the old single-prompt shape."""
    raw = drafted.get("prompts") or ([drafted["prompt"]] if drafted.get("prompt") else [])
    return [str(p).strip() for p in raw if str(p).strip()][:3]


# ~3k tokens of facts; leaves headroom under Groq's ~8k request TPM for
# system prompt + completion on openai/gpt-oss-120b free tier.
_LLM_DIGEST_CHARS = 12_000


def _fit_digest(digest: str, *, limit: int = _LLM_DIGEST_CHARS) -> str:
    if len(digest) <= limit:
        return digest
    cut = digest[:limit].rsplit("\n", 1)[0].rstrip()
    return f"{cut}\n…[truncated for model limits; full facts remain on the project]"


__all__ = [
    "build_phase_graph",
    "initial_state",
    "PhaseState",
    "DONE_PHASE",
    "SKIP_LABEL",
    "SKIPPED",
]
