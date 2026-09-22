"""LLM advice for a single open fact conflict (advisory until Keep A/B)."""

from __future__ import annotations

from typing import Any

from app.agents.inference import PURPOSE_TAG, complete_json
from app.agents.interview import is_delegate_answer


def _both_sides_requested(text: str) -> bool:
    low = text.lower()
    return any(
        p in low
        for p in (
            "both",
            "have both",
            "keep both",
            "can we do both",
            "option 1 and 2",
            "a and b",
        )
    )


def advise_single_conflict(
    inference: Any,
    *,
    model: str,
    row: dict,
    user_message: str = "",
) -> dict[str, str]:
    """Return pick (a|b), why, and a short reply for one conflict row."""
    card_a = row["card_a"]["body"]
    card_b = row["card_b"]["body"]
    user = (user_message or "").strip()
    if _both_sides_requested(user):
        return {
            "pick": "",
            "why": "",
            "reply": (
                "These two statements contradict each other, so we can only keep one as "
                "a project fact. Pick **Keep A** or **Keep B** below — or tell me which "
                "side fits your product decision and I'll recommend one."
            ),
        }
    if is_delegate_answer(user) and not user:
        user = "you decide — pick the better option for this MVP"

    advice = complete_json(
        inference,
        model=model,
        system=(
            f"{PURPOSE_TAG} conflict_advice\n"
            "User is resolving ONE fact conflict. Recommend which statement to keep (A or B). "
            "If the user stated a product decision, align with it. "
            "If they ask for both, explain only one can be kept. "
            "Never say you already applied, kept, or resolved anything — recommendations only. "
            'Return {"reply": str, "pick": "a"|"b", "why": str}. '
            "reply: 1 sentence framing the recommendation. why: one short reason."
        ),
        user=(
            f"A) {card_a}\nB) {card_b}\n\n"
            + (f"User: {user}" if user else "User: (no message — suggest the stronger MVP default)")
        ),
    )
    pick = str(advice.get("pick") or "").strip().lower()
    if pick not in {"a", "b"}:
        pick = "b"
    why = str(advice.get("why") or "").strip()
    reply = str(advice.get("reply") or "").strip()
    if not reply:
        reply = f"I'd keep **{pick.upper()}** for this conflict."
    return {"pick": pick, "why": why, "reply": reply}


def format_advice_message(advice: dict[str, str]) -> str:
    pick = str(advice.get("pick") or "").strip().lower()
    why = str(advice.get("why") or "").strip()
    reply = str(advice.get("reply") or "").strip()
    lines = [reply] if reply else []
    if pick in {"a", "b"} and why:
        lines.append(f"**Recommendation: Keep {pick.upper()}** — {why}")
    lines.append("Click **Keep A** or **Keep B** on the card to confirm.")
    return "\n\n".join(line for line in lines if line)
