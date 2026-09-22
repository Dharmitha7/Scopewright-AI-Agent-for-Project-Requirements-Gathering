"""Per-area coverage rubrics for interview ask/turn prompts."""

# ruff: noqa: E501

from __future__ import annotations

from functools import lru_cache

_RUBRICS: dict[tuple[str, str], str] = {
    ("planning", "business_need"): """
## Business need & vision — coverage rubric
**Essential before area_covered=true:**
- Who the product is for (user/stakeholder type)
- What problem or outcome it addresses (one clear sentence)
**Partial (answer_completeness=partial):** only audience OR only problem named; vague "make things easier"
**Not covered:** user says "I don't know" without substance; single word; unrelated tangent
**Close only when:** essentials are stated OR user explicitly confirms a recorded summary is complete
""",
    ("planning", "scope"): """
## Scope & exclusions — coverage rubric
**Essential:** what is IN v1/MVP (concrete capabilities or boundaries) AND what is OUT (at least one exclusion or "none stated")
**Partial:** only in-scope list without exclusions; or vague "core features"
**Ask follow-up:** user picks one chip from a multi-part scope question — confirm the rest
""",
    ("planning", "stakeholders"): """
## Stakeholders — coverage rubric
**Essential:** at least one decision-maker/sponsor AND at least one end-user or operator role with involvement
**Partial:** names only without roles; roles without who decides
""",
    ("planning", "risks"): """
## Risks — coverage rubric
**Essential:** at least two distinct risks OR user confirms proposed risk list; each with mitigation or acceptance
**Partial:** one risk only; risks with no mitigation when user should know
**Confirm mode:** "Yes" only closes if the listed risks were shown and user unambiguously confirms
""",
    ("requirements", "product_boundary"): """
## Product boundary — coverage rubric
**Essential:** user confirms inherited charter scope matches intent OR states specific boundary changes
**Do not re-litigate** entire charter — one confirm question is enough if facts already match uploads
""",
    ("requirements", "users_goals"): """
## Who it's for & why — coverage rubric
**Essential:** at least two distinct user types/personas AND primary goal per persona (what they need to accomplish)
**Partial:** one persona; goals without workflows
""",
    ("requirements", "tasks_scenarios"): """
## User flows — coverage rubric
**Essential:** at least one end-to-end happy-path scenario with steps AND expected system behavior at key steps
**Also required before area_covered=true:** user explicitly confirms no other primary flows remain for v1, OR a second distinct flow is captured
**Partial:** feature list without flow; one step only; one flow documented after a "which/first" question without closure
**Do not close** after only one flow if the question used "first", "which", or "another" unless user confirms that is everything
""",
    ("requirements", "failure_paths"): """
## Errors & recovery — coverage rubric
**Essential:** what happens on failure (error, retry, fallback) for at least one critical step from user flows
**Also required:** if the question asked which step or failure mode, confirm no other critical failures need coverage OR capture another
**Partial:** "show an error" without recovery behavior
""",
    ("requirements", "rules_calculations"): """
## Business rules — coverage rubric
**Essential:** at least one concrete business rule, threshold, or calculation AND who owns/changes it
**Partial:** rule named without threshold or owner
""",
    ("requirements", "data"): """
## Data & records — coverage rubric
**Essential:** core entities (nouns stored), primary source per entity, key relationships between entities
**Partial:** one entity only; audit/logging mentioned without events or retention stance
**Edge case:** user selects one audit event type — ask whether other event categories apply before closing
""",
    ("requirements", "external_interfaces"): """
## Integrations — coverage rubric
**Essential:** named external system(s), data direction (in/out), format or API style, failure/fallback behavior
**Partial:** system named without failure handling
""",
    ("requirements", "quality_targets"): """
## Performance & reliability — coverage rubric
**Essential:** at least one measurable target IF user knows it; otherwise explicit "not specified yet" after one ask
**Do not invent** SLAs or latency numbers — mark gap and move on only after user declines to specify
""",
    ("requirements", "constraints_compliance"): """
## Compliance & security — coverage rubric
**Essential:** named constraints (regulatory, security, residency, policy) that apply; only regimes evidence or user states
**Partial:** "must be secure" without specific standard only if user cannot name one after follow-up
""",
}


@lru_cache(maxsize=32)
def area_rubric(phase_key: str, area_key: str, *, fallback_guidance: str = "") -> str:
    rubric = _RUBRICS.get((phase_key, area_key), "").strip()
    if rubric:
        return rubric
    if fallback_guidance:
        return f"## {area_key}\n{fallback_guidance}"
    return f"## {area_key}\nCover the essentials for this area before marking area_covered=true."
