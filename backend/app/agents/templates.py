"""Phase templates as data (D18). The engine is phase-agnostic; these rows drive it.

v1 ships templates as code constants; the storage lane moves them to versioned
DB rows later without touching the graph.

Field roles (no overlap):
- hint: one-line UI sublabel for humans
- guidance: what to explore in interview / ingestion (per-area topic spec)
- rubrics.py: when an area is done (essentials / partial / not covered)
- skills/*.md: global interview style only
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoverageArea:
    key: str
    label: str
    hint: str
    guidance: str


@dataclass(frozen=True)
class PhaseTemplate:
    key: str
    label: str
    document: str
    areas: tuple[CoverageArea, ...]
    next_phase: str | None = None
    seeded_from_previous: bool = False
    extras_allowed: bool = True
    auto_research: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


PLANNING = PhaseTemplate(
    key="planning",
    label="Planning",
    document="Project Charter",
    areas=(
        CoverageArea(
            key="business_need",
            label="Business need & vision",
            hint="What problem this solves and for whom",
            guidance=(
                "Explore: who the product is for; the problem or outcome it addresses; "
                "what the product is in one plain sentence.\n"
                "Avoid: success metrics unless the user already stated them; feature lists; "
                "tech stack or implementation choices.\n"
                "When thin: propose a one-sentence need from the brief or uploads, then ask "
                "the user to confirm or correct — do not interrogate for numbers."
            ),
        ),
        CoverageArea(
            key="scope",
            label="Scope & exclusions",
            hint="What's in v1 and what's explicitly out",
            guidance=(
                "Explore: concrete capabilities or outcomes in v1; at least one explicit "
                "exclusion or deferred item; boundaries between MVP and later phases.\n"
                "Avoid: exhaustive feature backlogs; asking for a full roadmap.\n"
                "When thin: propose a minimal v1 scope from context, then confirm — one "
                "in-scope list plus one exclusion is enough to start."
            ),
        ),
        CoverageArea(
            key="stakeholders",
            label="Stakeholders",
            hint="Who decides, uses it, and builds it",
            guidance=(
                "Explore: who sponsors or decides; who uses or operates the product daily; "
                "technical or delivery partners; each person's role and involvement level.\n"
                "Avoid: org-chart trivia unrelated to the product; inventing names.\n"
                "When thin: infer likely roles from the brief, propose 2–3 stakeholders, "
                "ask who is missing or wrong."
            ),
        ),
        CoverageArea(
            key="risks",
            label="Risks",
            hint="What could block or derail the project",
            guidance=(
                "Explore: technical, dependency, timeline, adoption, and compliance risks "
                "grounded in this project; a brief mitigation or acceptance per risk.\n"
                "Avoid: generic risk catalogs; inventing compliance regimes.\n"
                "When thin: draft 3–5 risks from brief and uploads for confirm mode — user "
                "adds only concerns they already know."
            ),
        ),
    ),
    next_phase="requirements",
    auto_research=True,
    notes=(
        "Feasibility is optional and never gating (D24).",
        "Resources/timeline/budget are out of v1 Planning (recorded deviation 1).",
    ),
)

REQUIREMENTS = PhaseTemplate(
    key="requirements",
    label="Requirements",
    document="Requirements deliverables",
    areas=(
        CoverageArea(
            key="product_boundary",
            label="Product boundary",
            hint="Confirm what's in or out of v1",
            guidance=(
                "Explore: whether the accepted Charter scope still matches intent; any "
                "specific boundary changes for Requirements depth.\n"
                "Avoid: re-litigating the whole Charter or re-asking scope already accepted "
                "(D27).\n"
                "When facts exist: one confirm question — user confirms or names deltas only."
            ),
        ),
        CoverageArea(
            key="users_goals",
            label="Who it's for & why",
            hint="Main user types and what they need to accomplish",
            guidance=(
                "Explore: at least two distinct personas or user types; primary goal each "
                "is trying to accomplish; motivations or constraints that shape their work.\n"
                "Avoid: collapsing everyone into 'users'; UI layout opinions before goals.\n"
                "When thin: start from Charter stakeholders, ask who else uses the product "
                "and what each type needs to get done."
            ),
        ),
        CoverageArea(
            key="tasks_scenarios",
            label="User flows",
            hint="Step-by-step how people use the product",
            guidance=(
                "Explore: end-to-end happy-path scenario(s) with trigger, steps, and expected "
                "system behavior at key steps; confirm when no other primary flows remain for v1.\n"
                "Avoid: feature bullet lists without sequence; one-step fragments; closing after "
                "one flow when the user was asked 'which/first' without a closure question.\n"
                "When thin: pick the most important persona and walk through their primary task "
                "step by step; then ask whether other primary flows exist."
            ),
        ),
        CoverageArea(
            key="failure_paths",
            label="Errors & recovery",
            hint="What happens when something goes wrong",
            guidance=(
                "Explore: failure modes for at least one critical step from user flows — bad "
                "input, timeouts, partial completion, permission denied; recovery or fallback.\n"
                "Avoid: generic 'show an error' with no recovery; speculative edge cases far "
                "from stated flows.\n"
                "When thin: anchor on the main flow already captured and ask what should "
                "happen when that step fails."
            ),
        ),
        CoverageArea(
            key="rules_calculations",
            label="Business rules",
            hint="Logic, thresholds, and validation the system must enforce",
            guidance=(
                "Explore: concrete rules, thresholds, formulas, or validation; who owns or "
                "may change each rule; exceptions the business cares about.\n"
                "Avoid: restating obvious UI validation with no business meaning.\n"
                "When thin: ask for the one rule that would cause the most harm if wrong."
            ),
        ),
        CoverageArea(
            key="data",
            label="Data & records",
            hint="What information is stored and where it comes from",
            guidance=(
                "Explore: core entities (nouns the system stores); primary source per entity; "
                "key relationships; retention or volume only if the user knows.\n"
                "Avoid: full data-model design; inventing retention periods.\n"
                "When thin: list the 3–5 most important things the system must remember."
            ),
        ),
        CoverageArea(
            key="external_interfaces",
            label="Integrations",
            hint="Other systems, APIs, and data handoffs",
            guidance=(
                "Explore: named external systems; data direction (in/out); format or API style; "
                "what happens when an integration fails.\n"
                "Avoid: naming vendors or protocols not in evidence; assuming cloud services.\n"
                "When thin: ask which existing system this must talk to first."
            ),
        ),
        CoverageArea(
            key="quality_targets",
            label="Performance & reliability",
            hint="Speed, uptime, and scale — numbers if you have them",
            guidance=(
                "Explore: response-time, throughput, availability, or capacity targets only "
                "when the user or evidence states them.\n"
                "Avoid: inventing SLAs, latency numbers, or 'industry standard' defaults.\n"
                "When unknown: one ask, then record 'not specified' and move on."
            ),
        ),
        CoverageArea(
            key="constraints_compliance",
            label="Compliance & security",
            hint="Laws, policies, and security requirements",
            guidance=(
                "Explore: named regulatory, security, residency, or policy constraints from "
                "the user or uploads; technology constraints that bound design.\n"
                "Avoid: vague 'must be secure' without a named standard unless user truly "
                "cannot name one after follow-up.\n"
                "When thin: ask which rules or audits already apply to this product."
            ),
        ),
    ),
    next_phase=None,
    seeded_from_previous=True,
)

TEMPLATES: dict[str, PhaseTemplate] = {t.key: t for t in (PLANNING, REQUIREMENTS)}

FIRST_PHASE = PLANNING.key
DONE_PHASE = "done"


def get_template(phase: str) -> PhaseTemplate:
    return TEMPLATES[phase]
