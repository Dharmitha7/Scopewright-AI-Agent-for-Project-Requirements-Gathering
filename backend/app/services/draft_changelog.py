"""Draft changelog helpers (D83) — 3–5 bullets prepended only on draft markdown."""

from __future__ import annotations

import re

from app.agents.inference import PURPOSE_TAG, get_inference
from app.core.config import Settings

CHANGELOG_START = "<!-- crewlane:draft-changelog -->"
CHANGELOG_END = "<!-- /crewlane:draft-changelog -->"


def strip_changelog(markdown: str) -> str:
    """Remove draft changelog block for final exports (never ship on finals)."""
    if CHANGELOG_START not in markdown:
        return markdown
    pattern = re.compile(
        re.escape(CHANGELOG_START) + r".*?" + re.escape(CHANGELOG_END) + r"\s*",
        re.DOTALL,
    )
    return pattern.sub("", markdown).lstrip()


def prepend_changelog(markdown: str, bullets: list[str]) -> str:
    clean = strip_changelog(markdown)
    lines = [CHANGELOG_START, "## Changes from previous draft", ""]
    for b in bullets[:5]:
        text = b.strip().lstrip("-• ").strip()
        if text:
            lines.append(f"- {text}")
    lines.extend(["", CHANGELOG_END, "", clean])
    return "\n".join(lines)


def draft_change_bullets(
    settings: Settings,
    *,
    pack_title: str,
    previous: str,
    current: str,
) -> list[str]:
    """Ask the model for 3–5 bullets; fall back to a generic note."""
    prev_body = strip_changelog(previous).strip()
    curr_body = strip_changelog(current).strip()
    if not prev_body:
        return ["Initial draft of this deliverable."]
    if prev_body == curr_body:
        return ["No material wording changes from the previous draft."]

    inference = get_inference(settings)
    prompt = (
        f"Compare the previous and new draft of '{pack_title}'. "
        "Return ONLY 3 to 5 short markdown bullet lines (each starting with '- ') "
        "describing what changed for a BA. No preamble."
    )
    try:
        raw = inference.complete(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": PURPOSE_TAG
                    + "draft_changelog\n"
                    + "You summarize document diffs as brief bullets for a BA.",
                },
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n--- PREVIOUS ---\n{prev_body[:6000]}\n\n"
                        f"--- NEW ---\n{curr_body[:6000]}"
                    ),
                },
            ],
        )
    except Exception:
        return [
            "Deliverable regenerated from the current project cards.",
            "Review the full draft for detailed edits.",
        ]

    bullets = [
        line.strip()
        for line in (raw or "").splitlines()
        if line.strip().startswith("-")
    ]
    if len(bullets) < 3:
        return [
            "Deliverable regenerated from the current project cards.",
            "Structure or wording updated versus the previous draft.",
            "Review the full draft before accepting.",
        ]
    return bullets[:5]
