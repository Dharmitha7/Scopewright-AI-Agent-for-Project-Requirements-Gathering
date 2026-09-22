from app.agents.readiness import (
    SKIPPED,
    assess_readiness,
    checklist_readiness_score,
    threshold_for,
)
from app.agents.templates import PLANNING


def test_threshold_for_planning() -> None:
    assert threshold_for("planning") == 70
    assert threshold_for("requirements") == 70


def test_checklist_score_weights_skipped() -> None:
    coverage = {
        "a": "answered",
        "b": "skipped",
        "c": "answered",
        "d": "answered",
    }
    assert checklist_readiness_score(coverage) == 75


def test_checklist_readiness_score_empty() -> None:
    assert checklist_readiness_score({}) == 0


def test_assess_readiness_blocks_on_skipped() -> None:
    result = assess_readiness(
        inference=object(),
        model="scripted",
        template=PLANNING,
        digest="A clinic booking tool.",
        coverage={"business_need": SKIPPED, "scope": "answered"},
        facts_by_area={"scope": ["v1 is rescheduling only"]},
    )
    assert not result.can_draft
    assert "business_need" in result.blocking_areas
