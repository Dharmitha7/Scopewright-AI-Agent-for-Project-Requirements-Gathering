"""Inference backends (D28: Groq, model-agnostic by config).

GroqInference is the real path. ScriptedInference keeps the app runnable and
testable with no API key: deterministic, honest about being a script.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.adapters.groq_client import GroqClientPool, resolved_groq_api_keys
from app.core.config import Settings

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)  # llm_usage lines must show under uvicorn's default WARNING root

PURPOSE_TAG = "#purpose:"


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCompletion:
    """Result of a tool-eligible completion: either direct content, or a
    request to run a tool - never both, and callers must not offer tools
    again on any follow-up call (bounded, no agentic loop)."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

_AFFIRMATIVE_WORDS = frozenset(
    {
        "yes",
        "correct",
        "confirmed",
        "right",
        "yep",
        "yeah",
        "sure",
        "ok",
        "okay",
        "good",
        "fine",
        "accurate",
        "exactly",
        "absolutely",
        "indeed",
        "approve",
        "matches",
    }
)

_JSON_TOOL_NAMES = frozenset({"json", "respond", "response"})


def _purpose_tag(messages: list[dict[str, Any]]) -> str:
    """Read the '#purpose:' line every call site's system prompt carries
    (originally added so ScriptedInference could branch) - reused here to
    label real Groq usage logs by call site with no changes to callers."""
    system = messages[0]["content"] if messages else ""
    for line in system.splitlines():
        if line.startswith(PURPOSE_TAG):
            return line.removeprefix(PURPOSE_TAG).strip()
    return ""


def _log_usage(usage: Any, *, purpose: str, model: str) -> None:
    if usage is None:
        return
    log.info(
        "llm_usage purpose=%s model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
        purpose,
        model,
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        getattr(usage, "total_tokens", None),
    )


def recover_json_tool_completion(exc: BaseException) -> ToolCompletion | None:
    """Groq models sometimes emit structured JSON as a phantom ``json`` tool call.

    When the provider rejects that (tool not in request.tools), the payload is
    often still present in ``failed_generation`` — recover it instead of failing
    the whole turn.
    """
    import groq

    if not isinstance(exc, groq.BadRequestError):
        return None
    body = exc.body if isinstance(exc.body, dict) else {}
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    if err.get("code") != "tool_use_failed":
        return None
    raw = str(err.get("failed_generation") or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    name = str(payload.get("name") or "").lower()
    args = payload.get("arguments")
    if name in _JSON_TOOL_NAMES and isinstance(args, dict):
        return ToolCompletion(content=json.dumps(args), tool_calls=[])
    if "intent" in payload or "reply" in payload:
        return ToolCompletion(content=json.dumps(payload), tool_calls=[])
    return None


class GroqInference:
    def __init__(self, pool: GroqClientPool) -> None:
        self._pool = pool

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {"messages": messages, "model": model}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        def _call(client: Any) -> str:
            completion = client.chat.completions.create(**kwargs)
            _log_usage(
                getattr(completion, "usage", None),
                purpose=_purpose_tag(messages),
                model=model,
            )
            return completion.choices[0].message.content or ""

        return self._pool.execute(_call)

    def complete_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> ToolCompletion:
        """One bounded tool-eligible call. ``tool_choice="auto"`` lets the
        model answer directly or request a tool - the caller decides what
        happens next; this method never loops or calls the model again."""
        kwargs: dict[str, Any] = {
            "messages": messages,
            "model": model,
            "tools": tools,
            "tool_choice": "auto",
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        def _call(client: Any) -> ToolCompletion:
            completion = client.chat.completions.create(**kwargs)
            _log_usage(
                getattr(completion, "usage", None),
                purpose=_purpose_tag(messages),
                model=model,
            )
            message = completion.choices[0].message
            calls: list[ToolCall] = []
            for raw_call in message.tool_calls or []:
                try:
                    arguments = json.loads(raw_call.function.arguments or "{}")
                except (ValueError, TypeError):
                    arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                calls.append(
                    ToolCall(id=raw_call.id, name=raw_call.function.name, arguments=arguments)
                )
            return ToolCompletion(content=message.content, tool_calls=calls)

        try:
            return self._pool.execute(_call)
        except BaseException as exc:
            recovered = recover_json_tool_completion(exc)
            if recovered is not None:
                log.warning("complete_with_tools: recovered JSON from phantom tool call")
                return recovered
            raise


def _scripted_story(*, title: str, what_seed: str) -> dict[str, Any]:
    return {
        "title": title,
        "what": f"As a user, I want {what_seed}, so that the goal is met.",
        "why": "Not stated.",
        "how": "Not stated.",
        "acceptance": {
            "happy": [
                {
                    "name": "Main success path",
                    "steps": [
                        {"keyword": "Given", "text": "the stated precondition"},
                        {"keyword": "When", "text": "the main action happens"},
                        {"keyword": "Then", "text": "the stated outcome occurs"},
                    ],
                }
            ],
            "sad": [
                {
                    "name": "Failure path",
                    "steps": [
                        {"keyword": "Given", "text": "Not stated."},
                        {"keyword": "When", "text": "Not stated."},
                        {"keyword": "Then", "text": "Not stated."},
                    ],
                }
            ],
        },
    }


class ScriptedInference:
    """No-key fallback with improved handlers for all purpose tags."""

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        del json_mode, max_tokens  # parity with GroqInference; unused here
        system = messages[0]["content"] if messages else ""
        last = messages[-1]["content"] if messages else ""
        purpose = ""
        for line in system.splitlines():
            if line.startswith(PURPOSE_TAG):
                purpose = line.removeprefix(PURPOSE_TAG).strip()
                break
        # Scripted facts stay verbatim with NO area: the caller's default_area
        # (the area being asked about) applies via facts_by_area. Hardcoding
        # "general" here sent every scripted fact outside the phase's areas,
        # which broke coverage attribution and produced empty snapshots.
        if purpose in ("turn", "turn_confirm"):
            if last.rstrip().endswith("?"):
                return json.dumps(
                    {
                        "intent": "aside",
                        "kind": "aside",
                        "confirmed": False,
                        "facts": [],
                        "area_covered": False,
                        "gaps": [],
                        "reply": "Scripted aside answer. Your question was: " + last[:200],
                    }
                )
            from app.agents.interview import (
                is_clarify_request,
                is_delegate_answer,
                is_explicit_skip,
                is_mostly_correct_add,
                is_process_meta,
                is_skip_answer,
            )

            if is_process_meta(last):
                return json.dumps(
                    {
                        "intent": "process_meta",
                        "kind": "answer",
                        "confirmed": False,
                        "facts": [],
                        "area_covered": False,
                        "gaps": [],
                        "reply": "Got it — I'll keep offering clickable options.",
                    }
                )
            if is_delegate_answer(last):
                return json.dumps(
                    {
                        "intent": "delegate",
                        "kind": "answer",
                        "confirmed": False,
                        "facts": [],
                        "area_covered": False,
                        "gaps": [],
                        "reply": "I'll propose something for you to confirm.",
                    }
                )
            if is_explicit_skip(last):
                return json.dumps(
                    {
                        "intent": "skip",
                        "kind": "answer",
                        "confirmed": False,
                        "facts": [],
                        "area_covered": False,
                        "gaps": [],
                        "reply": "Skipped for now — we'll revisit before drafting.",
                    }
                )
            if is_skip_answer(last):
                return json.dumps(
                    {
                        "intent": "answer",
                        "kind": "answer",
                        "confirmed": False,
                        "facts": [],
                        "area_covered": False,
                        "answer_completeness": "unclear",
                        "gaps": ["Need a concrete answer for this area"],
                        "reply": "Let me ask a narrower question.",
                        "followup_prompt": "What can you share about this area?",
                        "followup_options": ["I'll type below", "You decide for me", "Other"],
                    }
                )
            if is_mostly_correct_add(last) or is_clarify_request(last):
                return json.dumps(
                    {
                        "intent": "answer",
                        "kind": "answer",
                        "confirmed": False,
                        "facts": [],
                        "area_covered": False,
                        "answer_completeness": "partial",
                        "gaps": ["User wants to add or clarify"],
                        "reply": "What would you like to add or change?",
                        "followup_prompt": "What should we add or change?",
                        "followup_options": ["I'll type below", "Other"],
                    }
                )
            words = set(last.lower().split())
            confirmed = purpose == "turn_confirm" and bool(words & _AFFIRMATIVE_WORDS)
            facts = (
                []
                if confirmed
                else [s.strip() for s in last.replace("\n", " ").split(".") if s.strip()]
            )
            substantive = bool(facts) and not is_skip_answer(last)
            covered = confirmed or substantive
            return json.dumps(
                {
                    "intent": "answer",
                    "kind": "answer",
                    "confirmed": confirmed,
                    "facts": [{"text": f} for f in facts[:5]],
                    "area_covered": covered,
                    "answer_completeness": "complete" if covered else "unclear",
                    "gaps": [],
                    "reply": f"Recorded {len(facts)} fact(s)." if facts else "Confirmed.",
                }
            )
        if purpose == "readiness":
            has_skipped = "[skipped]" in last
            answered = last.count("[answered]")
            blocking: list[str] = []
            if has_skipped:
                for line in last.splitlines():
                    if "[skipped]" in line and line.startswith("### "):
                        blocking.append(line.split()[0].removeprefix("###"))
            score = 82 if answered >= 3 and not has_skipped else 55
            return json.dumps(
                {
                    "overall_score": score,
                    "area_scores": {},
                    "blocking_areas": blocking[:4],
                    "can_draft": score >= 70 and not blocking,
                    "summary": "Scripted readiness assessment.",
                }
            )
        if purpose == "gate_turn":
            low = last.lower()
            if any(p in low for p in ("revise", "revisit", "thin", "change")):
                area = "risks" if "risk" in low else None
                return json.dumps(
                    {
                        "intent": "revise",
                        "reply": "Got it — let's revisit that area.",
                        "area": area,
                    }
                )
            if any(p in low for p in ("accept", "looks good", "ship it", "approve")):
                return json.dumps(
                    {
                        "intent": "accept",
                        "reply": "Accepting the gate.",
                        "area": None,
                    }
                )
            if last.rstrip().endswith("?"):
                return json.dumps(
                    {
                        "intent": "qa",
                        "reply": "Scripted gate Q&A based on the draft preview.",
                        "area": None,
                    }
                )
            return json.dumps(
                {
                    "intent": "ack",
                    "reply": "Noted — use the gate card when you're ready.",
                    "area": None,
                }
            )
        if purpose == "conflict_advice":
            low = last.lower()
            if "both" in low:
                return json.dumps(
                    {
                        "reply": (
                            "Only one statement can be kept — pick Keep A or Keep B on the card."
                        ),
                        "pick": "",
                        "why": "",
                    }
                )
            pick = "a" if "option 1" in low or "sms only" in low or "invoice" in low else "b"
            if "you decide" in low or "you can decide" in low:
                pick = "b"
            return json.dumps(
                {
                    "reply": "Here is my recommendation for this conflict.",
                    "pick": pick,
                    "why": "Aligned with your stated preference when possible.",
                }
            )
        if purpose == "retrieval_route":
            message = last.rsplit("User message:", 1)[-1].strip()
            should_retrieve = message.endswith("?")
            return json.dumps(
                {
                    "should_retrieve": should_retrieve,
                    "query": message if should_retrieve else "",
                    "reason": "scripted_question_router",
                }
            )
        if purpose == "grounding_check":
            answer = last.split("SOURCES:", 1)[0]
            return json.dumps(
                {
                    "supported": "[S" in answer,
                    "unsupported_claims": [],
                }
            )
        if purpose == "ingest_extract":
            # Relevance gate (junk-upload filtering) only appears in the
            # prompt once a scope digest exists (see ingestion._extract_system) -
            # scripted on_topic mirrors conflict_scan's word-overlap heuristic:
            # any shared 4+ letter word with the scope counts as on-topic.
            gate_active = "Project scope so far:" in system
            if gate_active:
                scope_text = system.split("Project scope so far:", 1)[1]
                scope_words = set(re.findall(r"[a-zA-Z]{4,}", scope_text.lower()))
                chunk_words = set(re.findall(r"[a-zA-Z]{4,}", last.lower()))
                if not (scope_words & chunk_words):
                    return json.dumps({"on_topic": False, "facts": []})
            facts = [s.strip() for s in last.replace("\n", " ").split(".") if s.strip()]
            result: dict[str, Any] = {"facts": [{"text": f} for f in facts[:8]]}
            if gate_active:
                result["on_topic"] = True
            return json.dumps(result)
        if purpose == "planning_redirect_check":
            # Same word-overlap heuristic as ingest_extract's on_topic and
            # conflict_scan: any Planning area whose guidance shares 2+
            # significant words with the message counts as a redirect match.
            i = system.find("Planning areas:")
            area_lines = system[i:].splitlines()[1:] if i != -1 else []
            last_words = set(re.findall(r"[a-zA-Z]{4,}", last.lower()))
            best_area, best_overlap = None, 0
            for line in area_lines:
                line = line.strip()
                if not line.startswith("- "):
                    break
                key, _, guidance = line[2:].partition(":")
                overlap = len(last_words & set(re.findall(r"[a-zA-Z]{4,}", guidance.lower())))
                if overlap > best_overlap:
                    best_area, best_overlap = key.strip(), overlap
            if best_area and best_overlap >= 2:
                return json.dumps(
                    {
                        "belongs_to_planning": True,
                        "planning_area": best_area,
                        "reason": f"This sounds like a {best_area} change, a Planning-level "
                        "concern rather than a Requirements detail.",
                    }
                )
            return json.dumps({"belongs_to_planning": False, "planning_area": "", "reason": ""})
        # Chunked stories path (outline → per-feature); keep legacy "stories" too.
        if purpose == "stories_outline":
            return json.dumps(
                {
                    "epics": [
                        {
                            "title": "Core flows (scripted)",
                            "features": [{"title": "Primary capability"}],
                        }
                    ]
                }
            )
        if purpose in ("stories_feature", "stories"):
            first = (last.splitlines() or ["the main task"])[0][:120]
            seed = first.removeprefix("Feature:").strip() or first
            if purpose == "stories_feature":
                return json.dumps(
                    {
                        "stories": [
                            _scripted_story(title="Complete the main task", what_seed=seed[:120])
                        ]
                    }
                )
            return json.dumps(
                {
                    "epics": [
                        {
                            "title": "Core flows (scripted)",
                            "features": [
                                {
                                    "title": "Primary capability",
                                    "stories": [
                                        _scripted_story(
                                            title="Complete the main task",
                                            what_seed=seed[:120],
                                        )
                                    ],
                                }
                            ],
                        }
                    ]
                }
            )
        if purpose == "name":
            return " ".join(last.split()[:6])[:120]
        if purpose == "critic":
            issues = (
                [
                    {
                        "severity": "medium",
                        "area": "general",
                        "note": "Scripted review: at least one statement is vague.",
                    }
                ]
                if "unknown" in last.lower()
                else []
            )
            return json.dumps({"issues": issues})
        if purpose == "conflict_scan":
            existing: list[str] = []
            new: list[str] = []
            bucket: list[str] | None = None
            for line in last.splitlines():
                if line.startswith("EXISTING"):
                    bucket = existing
                elif line.startswith("NEW"):
                    bucket = new
                elif bucket is not None and ":" in line:
                    bucket.append(line.split(":", 1)[1].strip().lower())

            def _negated(text: str) -> bool:
                return "exclud" in text or " not " in f" {text} "

            conflicts = [
                {"new": f"N{ni + 1}", "existing": f"E{ei + 1}"}
                for ni, n in enumerate(new)
                for ei, e in enumerate(existing)
                if len(set(n.split()) & set(e.split())) >= 2 and _negated(n) != _negated(e)
            ]
            return json.dumps({"conflicts": conflicts})
        if purpose == "feasibility":
            return (
                "Scripted feasibility summary — set GROQ_API_KEY and SERPAPI_KEY "
                "for live research.\n\n" + last[:600]
            )
        if purpose == "proposal":
            return json.dumps(
                {
                    "proposals": [
                        "Scripted MVP: ship the core user flow in v1.",
                        "Scripted exclusion: integrations and extras wait until after v1.",
                    ]
                }
            )
        if purpose == "question":
            return json.dumps(
                {
                    "prompts": [last[:400]],
                    "options": [["Option A", "Option B", "Option C", "Other"]],
                    "why": "Let's explore this area of the project.",
                }
            )
        if purpose == "risk_synthesis":
            return json.dumps(
                {
                    "risks": [
                        "Risk: Low patient adoption if rescheduling is harder than calling. "
                        "Mitigation: pilot with one clinic and measure completion rate.",
                        "Risk: Calendar integration may be unknown or brittle. "
                        "Mitigation: validate the scheduling API during planning.",
                    ]
                }
            )
        if purpose == "narrative":
            return (
                "## Scripted narrative\n\nSet GROQ_API_KEY for an LLM-composed document.\n\n"
                + last[:800]
            )
        if purpose == "read_back":
            return (
                "Here is what I have so far (scripted read-back — set GROQ_API_KEY "
                "for the real one):\n" + last[:800]
            )
        if purpose == "post_complete_turn":
            # Reached only via complete_json's follow-up call after a scripted
            # tool call in complete_with_tools below - JSON, not plain text.
            return json.dumps(
                {
                    "reply": (
                        "Scripted post-complete reply based on the project cards. "
                        "Use Redraft requirements to regenerate deliverables."
                    ),
                    "in_scope": True,
                }
            )
        if purpose == "draft_changelog":
            return (
                "- Regenerated deliverable from current project cards.\n"
                "- Updated section wording versus the previous draft.\n"
                "- Review the full draft before accepting."
            )
        return last[:400]

    def complete_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> ToolCompletion:
        del model, max_tokens  # parity with GroqInference; unused here
        system = messages[0]["content"] if messages else ""
        last = messages[-1]["content"] if messages else ""
        purpose = ""
        for line in system.splitlines():
            if line.startswith(PURPOSE_TAG):
                purpose = line.removeprefix(PURPOSE_TAG).strip()
                break
        if purpose in ("turn", "turn_confirm"):
            from app.agents.interview import is_out_of_scope_question

            if is_out_of_scope_question(last):
                payload = {
                    "intent": "aside",
                    "kind": "aside",
                    "in_scope": False,
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "gaps": [],
                    "reply": "scripted out-of-scope reply, discarded by the caller",
                }
                return ToolCompletion(content=json.dumps(payload), tool_calls=[])
            # Same deterministic split as complete()'s "turn" handling: a
            # question simulates the model reaching for evidence once,
            # anything else is answered directly with no tool call.
            if last.rstrip().endswith("?") and tools:
                tool = tools[0]["function"]
                return ToolCompletion(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="scripted-1",
                            name=tool["name"],
                            arguments={"query": last[:200]},
                        )
                    ],
                )
            from app.agents.interview import (
                is_clarify_request,
                is_delegate_answer,
                is_explicit_skip,
                is_mostly_correct_add,
                is_process_meta,
                is_skip_answer,
            )

            if is_process_meta(last):
                payload = {
                    "intent": "process_meta",
                    "kind": "answer",
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "gaps": [],
                    "reply": "Got it — I'll keep offering clickable options.",
                }
            elif is_delegate_answer(last):
                payload = {
                    "intent": "delegate",
                    "kind": "answer",
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "gaps": [],
                    "reply": "I'll propose something for you to confirm.",
                }
            elif is_explicit_skip(last):
                payload = {
                    "intent": "skip",
                    "kind": "answer",
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "gaps": [],
                    "reply": "Skipped for now — we'll revisit before drafting.",
                }
            elif is_skip_answer(last):
                payload = {
                    "intent": "answer",
                    "kind": "answer",
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "answer_completeness": "unclear",
                    "gaps": ["Need a concrete answer for this area"],
                    "reply": "Let me ask a narrower question.",
                    "followup_prompt": "What can you share about this area?",
                    "followup_options": ["I'll type below", "You decide for me", "Other"],
                }
            elif is_mostly_correct_add(last) or is_clarify_request(last):
                payload = {
                    "intent": "answer",
                    "kind": "answer",
                    "confirmed": False,
                    "facts": [],
                    "area_covered": False,
                    "answer_completeness": "partial",
                    "gaps": ["User wants to add or clarify"],
                    "reply": "What would you like to add or change?",
                    "followup_prompt": "What should we add or change?",
                    "followup_options": ["I'll type below", "Other"],
                }
            else:
                words = set(last.lower().split())
                confirmed = purpose == "turn_confirm" and bool(words & _AFFIRMATIVE_WORDS)
                facts = (
                    []
                    if confirmed
                    else [s.strip() for s in last.replace("\n", " ").split(".") if s.strip()]
                )
                substantive = bool(facts) and not is_skip_answer(last)
                covered = confirmed or substantive
                payload = {
                    "intent": "answer",
                    "kind": "answer",
                    "confirmed": confirmed,
                    "facts": [{"text": f} for f in facts[:5]],
                    "area_covered": covered,
                    "answer_completeness": "complete" if covered else "unclear",
                    "gaps": [],
                    "reply": f"Recorded {len(facts)} fact(s)." if facts else "Confirmed.",
                }
            return ToolCompletion(content=json.dumps(payload), tool_calls=[])
        if purpose == "post_complete_turn":
            from app.agents.interview import is_out_of_scope_question

            if is_out_of_scope_question(last):
                payload = {"reply": "scripted out-of-scope reply, discarded", "in_scope": False}
                return ToolCompletion(content=json.dumps(payload), tool_calls=[])
            if last.rstrip().endswith("?") and tools:
                tool = tools[0]["function"]
                return ToolCompletion(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="scripted-1", name=tool["name"], arguments={"query": last[:200]}
                        )
                    ],
                )
            # A declarative, in-scope, non-question message: same "any
            # sentence is a fact" heuristic as the interview's scripted
            # "turn" purpose (D90 - post-complete chat can now record facts).
            payload = {
                "reply": "Scripted post-complete reply based on the project cards.",
                "in_scope": True,
                "intent": "answer",
                "area": "general",
                "facts": [last],
            }
            return ToolCompletion(content=json.dumps(payload), tool_calls=[])
        return ToolCompletion(content=last[:400], tool_calls=[])


def get_inference(settings: Settings):
    keys = resolved_groq_api_keys(settings)
    if keys:
        return GroqInference(pool=GroqClientPool(keys))
    return ScriptedInference()


def facts_by_area(
    extraction: dict, *, default_area: str, valid_areas: set[str]
) -> dict[str, list[str]]:
    """Group extracted facts by coverage area; tolerates plain-string facts
    (the scripted path) and unknown area keys (fall back to 'general')."""
    grouped: dict[str, list[str]] = {}
    for fact in extraction.get("facts") or []:
        if isinstance(fact, dict):
            text = str(fact.get("text") or "").strip()
            area = str(fact.get("area") or default_area).strip() or default_area
        else:
            text = str(fact).strip()
            area = default_area
        if area not in valid_areas and area != "general":
            area = "general"
        if text:
            grouped.setdefault(area, []).append(text)
    return grouped


def parse_json_object(raw: str) -> dict[str, Any] | None:
    """Extract the first JSON object from model text; None if unusable."""
    if not raw:
        return None
    try:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        value = json.loads(raw[start : end + 1])
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def complete_json(
    inference,
    *,
    model: str,
    system: str,
    user: str,
    attempts: int = 1,
    json_mode: bool = False,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """LLM call that must return a JSON object; fails soft to {}.

    ``attempts`` > 1 retries with a repair turn (for nested/fragile schemas).
    ``json_mode`` asks Groq for response_format=json_object when supported.

    Two distinct failure shapes need the repair-turn retry, not just one:
    the model can return text that *we* fail to parse (parse_json_object()
    returns None - the original case this loop covered), or - when
    json_mode=True - Groq's own server-side validation can reject the
    completion outright before it ever comes back as a normal response,
    raising groq.BadRequestError (code "json_validate_failed") instead of
    returning text. That second shape used to escape this function
    entirely - none of the retry attempts ever ran, so a single bad
    generation (a real, observed failure on the large nested stories-pack
    schema) surfaced straight through the graph as an unhandled 500,
    skipping both this retry and the caller's own fallback (which only
    catches its own typed exception, not a raw provider error). Caught
    here now, same as invalid JSON: log it, feed the model's own
    (rejected) attempt back as context so the repair turn has something
    concrete to correct instead of starting blind, and keep retrying.

    Any other provider failure (rate limits, transient network errors, etc.)
    is soft-failed the same way rather than left to propagate - a single bad
    call must not 500 the whole gate Generate request over one of several
    packs/turns it's composing.
    """
    system_content = system + "\nRespond with a single JSON object only."
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user},
    ]
    last_raw = ""
    for attempt in range(max(1, attempts)):
        if attempt > 0:
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user},
                {"role": "assistant", "content": last_raw or "{}"},
                {
                    "role": "user",
                    "content": (
                        "Your previous reply was not valid JSON or was truncated. "
                        "Reply again with one complete JSON object only — "
                        "no markdown fences, no commentary. Keep the tree small."
                    ),
                },
            ]
        try:
            last_raw = inference.complete(
                model=model,
                messages=messages,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - provider errors vary; see docstring
            import groq

            if isinstance(exc, groq.BadRequestError):
                # Reuse the model's own rejected attempt as repair-turn
                # context instead of starting blind.
                log.warning(
                    "complete_json: provider rejected the completion (attempt %d): %s",
                    attempt + 1,
                    exc,
                )
                body = exc.body if isinstance(exc.body, dict) else {}
                last_raw = str((body.get("error") or {}).get("failed_generation") or "")
            else:
                # Rate limits, transient network errors, etc. - no useful
                # partial text to recover; soft-fail and retry blind rather
                # than let it propagate into a 500 on the gate Generate path.
                log.warning("complete_json attempt %s failed: %s", attempt + 1, exc)
                last_raw = ""
            continue
        parsed = parse_json_object(last_raw)
        if parsed is not None:
            return parsed
    return {}
