"""LLM draft-readiness scoring — holistic sufficiency, not checklist completion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.inference import PURPOSE_TAG, complete_json
from app.agents.rubrics import area_rubric
from app.agents.templates import PhaseTemplate

# Overall score (0–100) required before gate_emit / draft generation.
_THRESHOLDS: dict[str, dict[str, Any]] = {
    "planning": {
        "overall": 70,
        "floors": {"business_need": 60, "scope": 55},
    },
    "requirements": {
        "overall": 70,
        "floors": {"users_goals": 55, "tasks_scenarios": 55},
    },
}

ANSWERED = "answered"
SKIPPED = "skipped"
NA = "na"
PENDING = "pending"


@dataclass(frozen=True)
class ReadinessResult:
    overall_score: int
    area_scores: dict[str, int]
    blocking_areas: list[str]
    can_draft: bool
    summary: str


def threshold_for(phase: str) -> int:
    return int(_THRESHOLDS.get(phase, {}).get("overall", 70))


def floors_for(phase: str) -> dict[str, int]:
    return dict(_THRESHOLDS.get(phase, {}).get("floors", {}))


def _status_weight(status: str) -> float:
    if status == ANSWERED:
        return 1.0
    if status == NA:
        return 0.85
    if status == SKIPPED:
        return 0.0
    return 0.0


def _checklist_score(coverage: dict[str, str]) -> int:
    if not coverage:
        return 0
    total = sum(_status_weight(s) for s in coverage.values())
    return round(100 * total / len(coverage))


def checklist_readiness_score(coverage: dict[str, str]) -> int:
    """Cheap mid-interview estimate from checklist status — not gate quality."""
    return _checklist_score(coverage)


def assess_readiness(
    *,
    inference: Any,
    model: str,
    template: PhaseTemplate,
    digest: str,
    coverage: dict[str, str],
    facts_by_area: dict[str, list[str]],
) -> ReadinessResult:
    """Score whether recorded facts are enough to draft responsibly."""
    floors = floors_for(template.key)
    threshold = threshold_for(template.key)
    area_lines: list[str] = []
    for area in template.areas:
        status = coverage.get(area.key, PENDING)
        facts = facts_by_area.get(area.key) or []
        rubric = area_rubric(template.key, area.key, fallback_guidance=area.guidance)
        fact_block = "\n".join(f"  - {f}" for f in facts[:8]) if facts else "  - (none)"
        area_lines.append(
            f"### {area.key} [{status}]\n{rubric.strip()}\nRecorded facts:\n{fact_block}"
        )

    skipped = [k for k, v in coverage.items() if v == SKIPPED]
    if skipped:
        return ReadinessResult(
            overall_score=_checklist_score(coverage),
            area_scores={k: 0 for k in skipped},
            blocking_areas=skipped,
            can_draft=False,
            summary="Skipped areas must be revisited before drafting.",
        )

    user = (
        f"Phase: {template.label}\n"
        f"Document to draft: {template.document}\n\n"
        f"Project context:\n{digest[:8000]}\n\n"
        + "\n\n".join(area_lines)
    )
    result = complete_json(
        inference,
        model=model,
        system=(
            f"{PURPOSE_TAG} readiness\n"
            f"You judge whether there is enough substance to draft a {template.document}. "
            "Score each area 0–100 for draft sufficiency (not interview completion). "
            "Thin or missing facts → low score even if status is answered. "
            "Do not invent requirements. "
            f"overall_score = weighted average. can_draft=true only if overall_score>={threshold} "
            f"AND every floor is met: {floors}. "
            "blocking_areas = area keys that must improve before drafting (max 4). "
            'Return {"overall_score": int, "area_scores": {str: int}, '
            '"blocking_areas": [str], "can_draft": bool, "summary": str}.'
        ),
        user=user,
    )

    overall = int(result.get("overall_score") or _checklist_score(coverage))
    area_scores = {
        str(k): int(v) for k, v in (result.get("area_scores") or {}).items() if str(k).strip()
    }
    blocking = [str(k) for k in (result.get("blocking_areas") or []) if str(k).strip()][:4]
    can_draft = bool(result.get("can_draft"))

    for key, floor in floors.items():
        if key not in area_scores:
            continue
        if area_scores[key] < floor:
            can_draft = False
            if key not in blocking:
                blocking.append(key)

    if overall < threshold:
        can_draft = False

    if not blocking and not can_draft and overall < threshold:
        blocking = [
            a.key
            for a in template.areas
            if area_scores.get(a.key, 100) < 50 and coverage.get(a.key) != NA
        ][:2]

    return ReadinessResult(
        overall_score=max(0, min(100, overall)),
        area_scores=area_scores,
        blocking_areas=blocking,
        can_draft=can_draft,
        summary=str(result.get("summary") or "").strip(),
    )
