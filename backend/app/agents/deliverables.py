"""Requirements deliverable packs (data, like phase templates).

Selectable at the Requirements gate; Planning keeps a single Charter narrative.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliverablePack:
    key: str
    title: str
    purpose: str
    # llm | stories | deterministic
    kind: str


REQUIREMENTS_PACKS: tuple[DeliverablePack, ...] = (
    DeliverablePack(
        "requirements_summary",
        "Requirements Summary",
        "Executive usage — high-level overview",
        "llm",
    ),
    DeliverablePack(
        "business_requirements",
        "Business Requirements Specification",
        "High-level business requirements — waterfall execution",
        "llm",
    ),
    DeliverablePack(
        "functional_requirements",
        "Functional Requirements Specification",
        "Detailed functional requirements — waterfall execution",
        "llm",
    ),
    DeliverablePack(
        "non_functional_requirements",
        "Non-Functional Requirements",
        "Performance / security / compliance",
        "llm",
    ),
    DeliverablePack(
        "epics_features_stories",
        "Epics > Features > Stories (With Acceptance Criteria)",
        "Agile execution",
        "stories",
    ),
    DeliverablePack(
        "data_requirements",
        "Data Requirements",
        "Data entities, rules, mappings, validation",
        "llm",
    ),
    DeliverablePack(
        "integration_requirements",
        "Integration Requirements",
        "APIs / interfaces / events",
        "llm",
    ),
    DeliverablePack(
        "traceability_matrix",
        "Requirements Traceability Matrix",
        "End-to-end traceability (IDs → sources)",
        "deterministic",
    ),
    DeliverablePack(
        "user_journey",
        "User Journey Document",
        "Users and what they can do in the system",
        "llm",
    ),
    DeliverablePack(
        "quality_gap_report",
        "Requirements Quality & Gap Report",
        "Scores for completeness, ambiguity, conflicts, gaps",
        "deterministic",
    ),
)

PACK_BY_KEY = {p.key: p for p in REQUIREMENTS_PACKS}
PACK_KEYS = tuple(p.key for p in REQUIREMENTS_PACKS)


def validate_pack_selection(keys: list[str]) -> list[str]:
    """Return ordered unique valid keys; raises ValueError if empty or unknown."""
    seen: set[str] = set()
    ordered: list[str] = []
    for key in keys:
        if key not in PACK_BY_KEY:
            raise ValueError(f"unknown deliverable pack: {key}")
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    if not ordered:
        raise ValueError("select at least one deliverable pack")
    # Preserve catalog order for stable documents
    return [k for k in PACK_KEYS if k in seen]


def packs_for_widget() -> list[dict[str, str]]:
    return [
        {"key": p.key, "title": p.title, "purpose": p.purpose} for p in REQUIREMENTS_PACKS
    ]
