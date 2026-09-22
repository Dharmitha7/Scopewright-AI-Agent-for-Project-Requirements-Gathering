"""Coverage-area -> card kind mapping (D22). Data, not scattered ifs.

The graph passes coverage-area keys from `templates.py`; card kinds are the
locked D22 vocabulary. This module is the single place that translates one
into the other, for every phase template that exists today - the storage
lane's counterpart to templates.py being the single place phase shape lives.
"""

# Fallback for the "general" area (post-revise listening, graph.py's wait node
# with current_area is None) and any coverage-area key not in the map below.
GENERAL_KIND = "open_question"

AREA_KIND: dict[str, dict[str, str]] = {
    "planning": {
        "business_need": "business_need",
        "scope": "constraint",
        "stakeholders": "stakeholder",
        "risks": "risk",
    },
    "requirements": {
        "product_boundary": "constraint",
        "users_goals": "actor",
        "tasks_scenarios": "use_case",
        "failure_paths": "use_case",
        "rules_calculations": "requirement",
        "data": "data_entity",
        "external_interfaces": "interface",
        "quality_targets": "constraint",
        "constraints_compliance": "constraint",
    },
}


def kind_for(phase: str, area: str) -> str:
    """Card kind for a coverage-area key under a phase template."""
    return AREA_KIND.get(phase, {}).get(area, GENERAL_KIND)
