"""Interview policy helpers — chips, explicit skip, unsure follow-up, deference."""

from __future__ import annotations

import re

_PUNCT = re.compile(r"[^\w\s']+", re.UNICODE)

_EXPLICIT_SKIP_EXACT = {"skip"}
_EXPLICIT_SKIP_PHRASES = (
    "skip for now",
    "skip this question",
    "skip this",
    "skip it",
    "come back later",
    "come back to this",
)

_UNSURE_EXACT = {
    "idk",
    "n/a",
    "na",
    "nothing specific",
    "nothing",
    "thats it",
    "that's it",
    "that is it",
    "already told you",
    "i already told you",
    "i already told you right",
    "yes then that is it",
}

_UNSURE_PHRASES = (
    "i don't know",
    "i dont know",
    "don't know",
    "dont know",
    "not sure",
    "no idea",
    "nothing specific",
    "already told you",
)

_DELEGATE_PHRASES = (
    "you decide",
    "you can decide",
    "maybe you can decide",
    "can you decide",
    "you choose",
    "you pick",
    "whichever you think",
    "whatever you think",
    "whatever you want",
    "you decide for me",
    "whichever you think are best",
)

_PROCESS_META_PHRASES = (
    "multiple choice",
    "give me options",
    "give options",
    "clickable options",
    "show options",
    "i want options",
    "can you give options",
    "provide options",
)

_OUT_OF_SCOPE_PHRASES = (
    "capital of",
    "weather in",
    "weather today",
    "who won the",
    "favorite color",
    "tell me a joke",
)

# Selection/pick phrasing only — not broad "other/any" (those appear in closure questions).
_ENUM_MORE_QUESTION_PHRASES = (
    " first",
    "which one",
    "which primary",
    "which flow",
    "which persona",
    "which user type",
    "which step",
    "which integration",
    "which system",
    "which risk",
    "which entity",
    "which event",
    "which of",
    "pick one",
    "pick the",
    "start with which",
)

_ENUM_COMPLETE_PHRASES = (
    "that's the only",
    "that is the only",
    "thats the only",
    "only one",
    "only flow",
    "only primary",
    "no other",
    "nothing else",
    "just that one",
    "just this one",
    "that's everything",
    "that is everything",
    "that's all",
    "that is all",
    "these are the only",
    "there are no other",
    "there is no other",
    "don't have any other",
    "dont have any other",
)


def _norm(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", text.lower()).split())


def is_explicit_skip(text: str) -> bool:
    """User explicitly defers this question — allowed, revisited before draft."""
    n = _norm(text)
    if not n or len(n) > 80:
        return False
    if n in _EXPLICIT_SKIP_EXACT:
        return True
    return any(p in n for p in _EXPLICIT_SKIP_PHRASES) and not is_delegate_answer(text)


def is_unsure_answer(text: str) -> bool:
    """User is unsure — narrow follow-up; do not skip the area."""
    if is_explicit_skip(text):
        return False
    n = _norm(text)
    if not n or len(n) > 80:
        return False
    if n in _UNSURE_EXACT:
        return True
    return any(p in n for p in _UNSURE_PHRASES) and not is_delegate_answer(text)


def is_skip_answer(text: str) -> bool:
    """Alias for is_unsure_answer (legacy name in tests/inference)."""
    return is_unsure_answer(text)


def is_delegate_answer(text: str) -> bool:
    """User wants CrewLane to propose (scope/features/etc.)."""
    n = _norm(text)
    if not n:
        return False
    return any(p in n for p in _DELEGATE_PHRASES)


def is_process_meta(text: str) -> bool:
    """User is giving interview-process instructions, not product facts."""
    n = _norm(text)
    if not n or len(n) > 120:
        return False
    return any(p in n for p in _PROCESS_META_PHRASES)


_SELF_REFERENTIAL_FACT_RE = re.compile(
    r"^(the )?user (requested|asked|wants?|would like) to "
    r"(see|view|show|hear|know|repeat|summari[sz]e)",
    re.IGNORECASE,
)


def describes_users_own_request(text: str) -> bool:
    """A 'fact' that narrates the user's own message instead of stating a
    product fact — e.g. 'User requested to see the MVP scope list', invented
    from a meta-request like 'yes, show me the list'. Real product
    requirements are never phrased this way (they describe the system/user
    in the product, not the interview turn itself), so this is a safe,
    narrow backstop rather than a general 'contains show me' filter, which
    would also catch genuine product facts like 'the app should show me a
    daily progress list'."""
    return bool(_SELF_REFERENTIAL_FACT_RE.match(text.strip()))


def is_out_of_scope_question(text: str) -> bool:
    """Scripted heuristic for an obviously off-topic question (D81 scope guardrail)."""
    n = _norm(text)
    if not n:
        return False
    return any(p in n for p in _OUT_OF_SCOPE_PHRASES)


def question_implies_more_items(prompts: list[str]) -> bool:
    """True when a short interview question implied multiple items (e.g. 'describe first')."""
    for raw in prompts:
        text = (raw or "").strip()
        if not text or not text.endswith("?"):
            continue
        if len(text) > 220:
            continue
        p = _norm(text)
        if any(phrase in p for phrase in _ENUM_MORE_QUESTION_PHRASES):
            return True
    return False


def answer_signals_enumeration_complete(text: str) -> bool:
    """True when the user explicitly closes a multi-item enumeration."""
    n = _norm(text)
    if not n:
        return False
    return any(p in n for p in _ENUM_COMPLETE_PHRASES)


def enumeration_close_followup(area_label: str) -> tuple[str, list[str]]:
    label = area_label.lower()
    return (
        f"Are there other {label} we should capture for v1, or is that everything?",
        [
            "That's the only one for v1",
            "There's another — I'll describe it",
            "You decide what's essential",
            "Other",
        ],
    )


def guard_premature_enumeration_close(
    *,
    last_prompts: list[str],
    answer_text: str,
    area_label: str,
    area_covered: bool,
) -> tuple[bool, str | None, list[str] | None]:
    """Block area_covered when a plural/'first' question was not closed out."""
    if not area_covered:
        return False, None, None
    if not question_implies_more_items(last_prompts):
        return True, None, None
    if answer_signals_enumeration_complete(answer_text):
        return True, None, None
    prompt, opts = enumeration_close_followup(area_label)
    return False, prompt, opts


def is_mostly_correct_add(text: str) -> bool:
    """User affirmed but wants to add more — do not close the area yet."""
    n = _norm(text)
    return "mostly correct" in n or ("correct" in n and "but" in n and "add" in n)


def is_clarify_request(text: str) -> bool:
    """User rejected the confirm summary and wants to correct it."""
    n = _norm(text)
    return "let me clarify" in n or n.startswith("no let me") or n.startswith("no, let me")


def is_aside_question(text: str) -> bool:
    """True when the user is asking CrewLane about evidence — not answering the area."""
    raw = text.strip()
    if not raw:
        return False
    if raw.endswith("?"):
        return True
    n = _norm(text)
    starters = (
        "what did",
        "what does",
        "what do the",
        "what do you",
        "tell me what",
        "from the notes",
        "from the upload",
        "from the doc",
        "according to",
        "where does it say",
        "did the notes",
    )
    return any(n.startswith(s) for s in starters)


def default_options(area_key: str) -> list[str]:
    """Always-on chips when the model omits options."""
    by_area = {
        "business_need": [
            "Personal / own use",
            "Internal team tool",
            "Customer-facing product",
            "Other",
        ],
        "scope": [
            "Core logging only for v1",
            "Tracking + reminders for v1",
            "You decide a sensible MVP",
            "Other",
        ],
        "stakeholders": [
            "Just me",
            "Me and a small team",
            "End users plus a decision-maker",
            "Other",
        ],
        "risks": [
            "Yes, that's correct",
            "Mostly correct, but I'd add...",
            "No, let me clarify",
        ],
        "product_boundary": [
            "Yes, matches the charter",
            "Mostly, with a small change",
            "No, let me clarify",
        ],
    }
    return list(by_area.get(area_key) or ["Yes", "You decide for me", "Other"])


def ensure_option_lists(
    prompts: list[str],
    raw_options: object,
    *,
    area_key: str,
) -> list[list[str]]:
    """One option list per prompt. Never null — follow-ups always have chips."""
    defaults = default_options(area_key)
    tails = ["You decide for me"]
    lists: list[list[str] | None]
    if raw_options is None:
        lists = [None] * len(prompts)
    elif isinstance(raw_options, list):
        lists = []
        for item in raw_options:
            if item is None:
                lists.append(None)
            elif isinstance(item, list):
                lists.append([str(x).strip() for x in item if str(x).strip()])
            else:
                lists.append([str(item).strip()])
        while len(lists) < len(prompts):
            lists.append(None)
    else:
        lists = [None] * len(prompts)

    out: list[list[str]] = []
    for i, _ in enumerate(prompts):
        chosen = lists[i] if i < len(lists) else None
        if not chosen:
            chosen = list(defaults)
        merged = list(chosen)
        for tail in tails:
            if tail not in merged:
                merged.append(tail)
        if "Other" not in merged:
            merged.append("Other")
        out.append(merged)
    return out


def selection_mode_for(area_key: str, *, confirm: bool) -> str:
    if confirm:
        return "single"
    if area_key in {"scope", "stakeholders", "risks", "data", "constraints_compliance"}:
        return "multi"
    return "single"
