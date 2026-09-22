"""Snapshot documents (D60/D70): Charter + selectable Requirements packs.

Audit view stays deterministic from card pointers. Narratives freeze at Accept.
Requirements packs are composed only after the user selects them (gate option C).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.agents.deliverables import PACK_BY_KEY, DeliverablePack, validate_pack_selection
from app.agents.inference import (
    PURPOSE_TAG,
    GroqInference,
    complete_json,
    get_inference,
)
from app.agents.templates import PhaseTemplate
from app.core.config import get_settings
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.services import belief as belief_service
from app.services import cards as cards_service
from app.services import feasibility as feasibility_service
from app.services.document_export import (
    ExportMeta,
    build_export_meta,
    build_publish_meta,
    export_branded_docx,
    export_branded_pdf,
)

__all__ = [
    "ExportMeta",
    "build_export_meta",
    "build_publish_meta",
    "export_branded_docx",
    "export_branded_pdf",
]

logger = logging.getLogger(__name__)

# Embedded in pack markdown so Accept can refuse a broken generation without
# confusing it for genuine "facts were silent" Not stated placeholders.
PACK_FAILED_MARKER = "<!-- crewlane:pack_generation_failed -->"

# Brief pause between Groq story chunks — free-tier TPM is easy to trip when
# Generate selected also runs many other narrative packs in the same request.
_GROQ_STORY_PACE_S = 1.25

_STORY_AREAS = (
    "users_goals",
    "tasks_scenarios",
    "failure_paths",
    "rules_calculations",
    "quality_targets",
    "constraints_compliance",
)

STRICT_RULE = (
    "STRICTLY use only the facts below. Never add numbers, percentages, "
    "metrics, vendors, standards, or requirements the facts do not state - "
    "where the facts are silent, write 'Not stated.' "
    "Use markdown ## headings, paragraphs, and - bullet lists (no tables, "
    "no code blocks). "
)

_LLM_PACK_PROMPTS: dict[str, str] = {
    "requirements_summary": (
        "Write a Requirements Summary for executives: one short overview of "
        "purpose, users, scope, and outcomes. No FR numbering."
    ),
    "business_requirements": (
        "Write a Business Requirements Specification: business need, product "
        "boundary, stakeholders/users, business rules, and constraints in "
        "business language (not detailed FRs)."
    ),
    "functional_requirements": (
        "Write a Functional Requirements Specification. Number requirements "
        "FR-1, FR-2, …; add [Must], [Should], or [Could] only when facts "
        "explicitly state priority — otherwise omit any priority tag (never "
        "write [Unprioritized]). Do not repeat the document title; start with "
        "FR-1."
    ),
    "non_functional_requirements": (
        "Write Non-Functional Requirements (performance, security, compliance, "
        "quality targets). Number NFR-1, NFR-2, …; keep stated numbers exact."
    ),
    "data_requirements": (
        "Write Data Requirements: entities, sources, rules, validation, retention."
    ),
    "integration_requirements": (
        "Write Integration Requirements: external systems, APIs, events, failure "
        "behavior at each integration point."
    ),
    "user_journey": (
        "Write a User Journey Document: for each distinct user type, describe "
        "goals and main journeys as readable markdown (no diagrams)."
    ),
}


def generate_narrative(
    session: Session, project: Project, snapshot: Snapshot, template: PhaseTemplate
) -> None:
    """Planning path: compose and freeze a single Charter narrative."""
    audit = cards_service.render_snapshot(session, snapshot)
    narrative = _compose_charter(session, project, template, audit)
    snapshot.narrative = narrative.strip()
    snapshot.narratives = None
    session.commit()


def attach_pack_narratives(
    session: Session,
    snapshot: Snapshot,
    *,
    mode: str,
    packs: dict[str, str],
) -> None:
    """Freeze pre-generated Requirements packs onto the snapshot (D70/D84)."""
    mode = "separate"
    snapshot.narratives = {"mode": mode, "packs": packs, "combined": None}
    snapshot.narrative = _combine_packs(packs)
    session.commit()


def compose_selected_packs(
    session: Session,
    project: Project,
    template: PhaseTemplate,
    *,
    pack_keys: list[str],
    mode: str,
    critic_issues: list[dict] | None = None,
) -> dict[str, Any]:
    """Compose only the selected packs. Returns narratives payload + teaser."""
    keys = validate_pack_selection(pack_keys)
    # D84: separate-only; coerce any caller still passing combined.
    mode = "separate"
    audit = _live_audit(session, project, template)
    packs: dict[str, str] = {}
    for i, key in enumerate(keys):
        if i > 0:
            # Space Groq free-tier TPM between packs (stories already paces chunks).
            time.sleep(1.5)
        pack = PACK_BY_KEY[key]
        packs[key] = _compose_pack(session, project, template, pack, audit, critic_issues)
    combined = None
    display = _combine_packs(packs)
    failed_packs = [k for k, body in packs.items() if pack_body_failed(body)]
    return {
        "mode": mode,
        "packs": packs,
        "combined": combined,
        "teaser": _teaser(display),
        "display": display,
        "failed_packs": failed_packs,
    }


def apply_critic_findings(
    session: Session,
    project: Project,
    template: PhaseTemplate,
    composed: dict[str, Any],
    critic_issues: list[dict] | None,
) -> dict[str, Any]:
    """Refresh quality_gap_report (if selected) after post-compose critic review."""
    packs = dict(composed.get("packs") or {})
    if "quality_gap_report" in packs:
        pack = PACK_BY_KEY["quality_gap_report"]
        packs["quality_gap_report"] = (
            f"# {pack.title}\n\n"
            f"{_quality_gap_report(session, project, template, critic_issues)}"
        )
    display = _combine_packs(packs)
    return {**composed, "packs": packs, "display": display, "teaser": _teaser(display)}


def pack_body_failed(body: str | None) -> bool:
    return PACK_FAILED_MARKER in (body or "")


def snapshot_markdown(session: Session, snapshot: Snapshot, *, pack: str | None = None) -> str:
    if pack and snapshot.narratives:
        body = (snapshot.narratives.get("packs") or {}).get(pack)
        if body:
            return body
    if snapshot.narrative:
        return snapshot.narrative
    return cards_service.render_snapshot(session, snapshot)


def _live_audit(session: Session, project: Project, template: PhaseTemplate) -> str:
    lines = [f"# {template.document} (accepted facts)", ""]
    for area in template.areas:
        facts = cards_service.area_facts(session, project, area.key)
        lines.append(f"## {area.label}")
        if facts:
            lines.extend(f"- {f}" for f in facts)
        else:
            lines.append("- Not stated.")
        lines.append("")
    return "\n".join(lines)


def _compose_pack(
    session: Session,
    project: Project,
    template: PhaseTemplate,
    pack: DeliverablePack,
    audit: str,
    critic_issues: list[dict] | None,
) -> str:
    heading = f"# {pack.title}"
    try:
        if pack.kind == "stories":
            return f"{heading}\n\n{_stories_section(session, project)}"
        if pack.key == "traceability_matrix":
            return f"{heading}\n\n{_traceability_slim(session, project)}"
        if pack.key == "quality_gap_report":
            return f"{heading}\n\n{_quality_gap_report(session, project, template, critic_issues)}"
        prompt = _pack_instruction(pack.key)
        body = _llm_pack(project, audit, title=pack.title, instruction=prompt)
        body = _strip_duplicate_title(body.strip(), pack.title)
        if pack.key == "functional_requirements":
            body = _strip_unprioritized_tags(body)
        return f"{heading}\n\n{body}"
    except Exception as exc:
        logger.warning("pack %s compose failed: %s", pack.key, exc)
        return f"{heading}\n\n{_pack_failure_body(str(exc))}"


def _pack_failure_body(reason: str) -> str:
    return (
        f"{PACK_FAILED_MARKER}\n\n"
        "**Pack generation failed.** "
        f"{reason.strip() or 'Provider error or rate limit.'}\n\n"
        "Re-run **Generate selected**. Accept stays blocked while this pack is failed."
    )

def _strip_duplicate_title(body: str, title: str) -> str:
    """Drop a leading # title the LLM echoed — composer adds the pack heading."""
    lines = body.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return body
    first = lines[0].strip()
    normalized = title.strip().casefold()
    if first.casefold() in (f"# {normalized}", f"## {normalized}", normalized):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines)


def _strip_unprioritized_tags(body: str) -> str:
    return re.sub(r"\s*\[Unprioritized\]", "", body, flags=re.IGNORECASE)


def _pack_instruction(pack_key: str) -> str:
    return _LLM_PACK_PROMPTS.get(pack_key, f"Write the '{pack_key}' deliverable.")


def _llm_pack(project: Project, audit: str, *, title: str, instruction: str) -> str:
    settings = get_settings()
    return get_inference(settings).complete(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": (
                    f"{PURPOSE_TAG} narrative\n"
                    f"You write the '{title}' deliverable. {instruction} "
                    "Do not repeat the document title as a heading. "
                    + STRICT_RULE
                ),
            },
            {
                "role": "user",
                "content": f"Project: {project.brief}\n\nAccepted facts:\n{audit}",
            },
        ],
    )


def _compose_charter(
    session: Session, project: Project, template: PhaseTemplate, audit: str
) -> str:
    settings = get_settings()
    feasibility_input = ""
    report = feasibility_service.latest_report(session, project)
    if report:
        sources = "\n".join(
            f"- {s.get('title', '')} ({s.get('link', '')})" for s in report.get("sources", [])
        )
        feasibility_input = (
            "\n\nFeasibility research (include as its own '## Feasibility' section, "
            "keeping the dimension assessments, the GO/NO-GO recommendation, and the "
            "source links):\n" + report.get("summary", "") + "\nSources:\n" + sources
        )
    return get_inference(settings).complete(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": (
                    f"{PURPOSE_TAG} narrative\n"
                    f"You write the accepted {template.document} for a software project. "
                    "Structure: a one-paragraph executive summary, then one ## section per "
                    "coverage area with 2-4 well-written paragraphs synthesizing the facts, "
                    "then the Feasibility section when research is provided. "
                    "Write in third person, present tense - a formal deliverable. "
                    + STRICT_RULE
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Project: {project.brief}\n\nAccepted facts:\n{audit}{feasibility_input}"
                ),
            },
        ],
    )


def _stories_section(session: Session, project: Project) -> str:
    """Build epics → features → stories via small JSON chunks (Groq free-tier safe).

    One mega nested JSON call truncates easily and used to collapse into a silent
    "Not stated." — that looked like missing facts. Failures are explicit now.
    """
    settings = get_settings()
    inference = get_inference(settings)
    facts_blob = _collect_story_facts(session, project)
    try:
        tree = _build_stories_tree(
            inference,
            model=settings.groq_model,
            project_brief=project.brief or "",
            facts_blob=facts_blob,
        )
    except _StoriesGenerationError as exc:
        logger.warning("stories pack generation failed: %s", exc)
        return _stories_failure_body(str(exc))
    except Exception as exc:
        # Groq 400 json_validate_failed / 429 used to 500 the whole /gate request.
        logger.warning("stories pack provider error: %s", exc)
        return _stories_failure_body(str(exc))

    epics = tree.get("epics") or []
    if not epics:
        return "Not stated — no epics could be derived from accepted facts."
    return _stories_markdown(tree)


class _StoriesGenerationError(Exception):
    """Stories composer could not produce usable JSON after retries."""


def _collect_story_facts(session: Session, project: Project) -> str:
    lines: list[str] = []
    for area in _STORY_AREAS:
        for fact in cards_service.area_facts(session, project, area):
            lines.append(f"[{area}] {fact}")
    return "\n".join(lines) if lines else "No facts recorded."


def _pace_groq(inference: Any) -> None:
    if isinstance(inference, GroqInference):
        time.sleep(_GROQ_STORY_PACE_S)


def _stories_json(
    inference: Any,
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
) -> dict[str, Any]:
    return complete_json(
        inference,
        model=model,
        system=system,
        user=user,
        attempts=3,
        json_mode=True,
        max_tokens=max_tokens,
    )


def _build_stories_tree(
    inference: Any,
    *,
    model: str,
    project_brief: str,
    facts_blob: str,
) -> dict[str, Any]:
    outline = _stories_json(
        inference,
        model=model,
        system=(
            f"{PURPOSE_TAG} stories_outline\n"
            "From accepted facts only, propose a compact epic → feature outline. "
            "Infer feature titles from tasks/scenarios when needed. "
            "Never invent capabilities, timers, policies, or vendors. "
            "Prefer fewer, clearer epics/features over a large tree — "
            "keep the JSON small (free-tier friendly). "
            'Return {"epics":[{"title":str,"features":[{"title":str}]}]}.'
        ),
        user=f"Project: {project_brief}\n\nAccepted facts:\n{facts_blob}",
        max_tokens=2048,
    )
    raw_epics = outline.get("epics") or []
    if not isinstance(raw_epics, list) or not raw_epics:
        if facts_blob.strip() == "No facts recorded.":
            return {"epics": []}
        raise _StoriesGenerationError(
            "empty or invalid epic outline (model JSON missing/truncated)."
        )

    built: list[dict[str, Any]] = []
    story_count = 0
    first_chunk = True
    for epic in raw_epics:
        if not isinstance(epic, dict):
            continue
        epic_title = str(epic.get("title") or "Untitled").strip() or "Untitled"
        features_out: list[dict[str, Any]] = []
        for feature in epic.get("features") or []:
            if not isinstance(feature, dict):
                continue
            feature_title = (
                str(feature.get("title") or "Untitled").strip() or "Untitled"
            )
            if not first_chunk:
                _pace_groq(inference)
            first_chunk = False
            stories = _stories_for_feature(
                inference,
                model=model,
                project_brief=project_brief,
                facts_blob=facts_blob,
                epic_title=epic_title,
                feature_title=feature_title,
            )
            story_count += len(stories)
            features_out.append({"title": feature_title, "stories": stories})
        if features_out:
            built.append({"title": epic_title, "features": features_out})

    if not built:
        raise _StoriesGenerationError("outline had no usable features after parsing.")
    if story_count == 0:
        raise _StoriesGenerationError(
            "feature story calls returned no stories (JSON invalid/truncated)."
        )
    return {"epics": built}


def _stories_for_feature(
    inference: Any,
    *,
    model: str,
    project_brief: str,
    facts_blob: str,
    epic_title: str,
    feature_title: str,
) -> list[dict[str, Any]]:
    result = _stories_json(
        inference,
        model=model,
        system=(
            f"{PURPOSE_TAG} stories_feature\n"
            "Write user stories for ONE feature only, from accepted facts. "
            "Never invent capabilities, timers, policies, or vendors. "
            "Each story needs title, what (As a… I want… so that…), why, how. "
            "Acceptance criteria: happy and sad paths as scenario lists. "
            "Each scenario has name + steps; each step is "
            '{"keyword":"Given"|"When"|"Then"|"And","text":str}. '
            "Given/When/Then when facts support them; And is optional. "
            "If failure-path facts are missing, one sad scenario may say "
            "Not stated — do not invent failures. "
            "Prefer a small number of fact-backed stories; omit rather than invent. "
            'Return {"stories":[{"title":str,"what":str,"why":str,"how":str,'
            '"acceptance":{"happy":[{"name":str,"steps":[{"keyword":str,"text":str}]}],'
            '"sad":[{"name":str,"steps":[{"keyword":str,"text":str}]}]}}]}.'
        ),
        user=(
            f"Project: {project_brief}\n"
            f"Epic: {epic_title}\n"
            f"Feature: {feature_title}\n\n"
            f"Accepted facts:\n{facts_blob}"
        ),
        max_tokens=4096,
    )
    stories = result.get("stories") or []
    return [s for s in stories if isinstance(s, dict)]


def _stories_failure_body(reason: str) -> str:
    return (
        f"{PACK_FAILED_MARKER}\n\n"
        "**Stories generation failed.** "
        f"{reason.strip()}\n\n"
        "Re-run **Generate selected** (or Revise an area, then generate again). "
        "Do not Accept until this pack regenerates successfully — "
        "empty stories are not the same as ‘Not stated’ facts."
    )


def _stories_markdown(stories: dict) -> str:
    lines: list[str] = []
    epics = stories.get("epics") or []
    if not epics:
        return "Not stated."
    for epic in epics:
        lines.append(f"## Epic: {str(epic.get('title', 'Untitled')).strip()}")
        for feature in epic.get("features") or []:
            lines.append(f"### Feature: {str(feature.get('title', 'Untitled')).strip()}")
            for story in feature.get("stories") or []:
                title = str(story.get("title") or "Untitled").strip()
                lines.append(f"# User Story: {title}")
                lines.append("")
                for label, key in (("What", "what"), ("Why", "why"), ("How", "how")):
                    text = str(story.get(key) or "Not stated.").strip() or "Not stated."
                    lines.append(f"**{label}**")
                    lines.append(text)
                    lines.append("")
                lines.append("---")
                lines.append("")
                lines.append("## Acceptance Criteria")
                lines.append("")
                acceptance = story.get("acceptance") or {}
                if not isinstance(acceptance, dict):
                    acceptance = {}
                for path_label, path_key in (("Happy Path", "happy"), ("Sad Path", "sad")):
                    lines.append(f"### {path_label}")
                    lines.append("")
                    scenarios = acceptance.get(path_key) or []
                    if not isinstance(scenarios, list):
                        scenarios = []
                    if not scenarios:
                        lines.append("Not stated.")
                        lines.append("")
                        continue
                    for i, scenario in enumerate(scenarios, start=1):
                        # Deep LLM JSON: unlike epic/feature/story above (our
                        # own reconstructed dicts), scenarios/steps pass
                        # through raw - a model can return a bare string here
                        # instead of the requested object, especially on a
                        # schema this nested. Skip anything malformed rather
                        # than crash the whole pack (observed live).
                        if not isinstance(scenario, dict):
                            continue
                        name = str(scenario.get("name") or f"Scenario {i}").strip()
                        lines.append(f"**Scenario {i}: {name}**")
                        for step in scenario.get("steps") or []:
                            if not isinstance(step, dict):
                                continue
                            kw = str(step.get("keyword") or "Given").strip().title()
                            if kw not in {"Given", "When", "Then", "And"}:
                                kw = "Given"
                            text = str(step.get("text") or "").strip()
                            if text:
                                lines.append(f"- **{kw}** {text}")
                        lines.append("")
                lines.append("")
    return "\n".join(lines).strip()


def _traceability_slim(session: Session, project: Project) -> str:
    """FR/NFR/story-ish lines → source filenames (not a full card dump)."""
    sources = cards_service.card_sources(session, project)
    lines = [
        "Slim matrix generated from accepted facts and provenance links.",
        "",
        "| ID | Statement | Sources |",
        "| --- | --- | --- |",
    ]
    n = 0
    for card in cards_service.list_cards(session, project):
        if card.kind == belief_service.SOURCE_KIND or card.status == belief_service.RETIRED:
            continue
        if card.status not in ("accepted", "confirmed", "candidate"):
            continue
        n += 1
        origin = ", ".join(sources.get(card.id, [])) or "chat"
        stmt = card.body.replace("|", "/").replace("\n", " ")
        if len(stmt) > 160:
            stmt = stmt[:157] + "…"
        lines.append(f"| REQ-{n} | {stmt} | {origin} |")
    if n == 0:
        return "Not stated — no facts recorded."
    return "\n".join(lines)


def _quality_gap_report(
    session: Session,
    project: Project,
    template: PhaseTemplate,
    critic_issues: list[dict] | None,
) -> str:
    empty = [
        area.label
        for area in template.areas
        if not cards_service.area_facts(session, project, area.key)
    ]
    conflicts = belief_service.list_conflicts(session, project)
    issues = critic_issues or []
    total_areas = max(len(template.areas), 1)
    completeness = int(round(100 * (total_areas - len(empty)) / total_areas))
    high = sum(1 for i in issues if str(i.get("severity")) == "high")
    medium = sum(1 for i in issues if str(i.get("severity")) == "medium")
    ambiguity = max(0, 100 - high * 25 - medium * 10)
    conflict_score = 100 if not conflicts else max(0, 100 - 30 * len(conflicts))
    gap_score = max(0, 100 - int(round(100 * len(empty) / total_areas)))

    lines = [
        "## Scores",
        f"- **Completeness:** {completeness}/100 "
        f"({total_areas - len(empty)}/{total_areas} areas have facts)",
        f"- **Ambiguity:** {ambiguity}/100 "
        f"(from reviewer findings: {high} high, {medium} medium)",
        f"- **Conflicts:** {conflict_score}/100 ({len(conflicts)} open)",
        f"- **Gaps:** {gap_score}/100 ({len(empty)} empty areas)",
        "",
        "## Empty areas",
    ]
    if empty:
        lines.extend(f"- {label}" for label in empty)
    else:
        lines.append("- None")
    lines.extend(["", "## Open conflicts"])
    if conflicts:
        for c in conflicts:
            lines.append(
                f"- \"{c['card_a']['body']}\" vs \"{c['card_b']['body']}\""
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Reviewer findings"])
    if issues:
        for i in issues:
            lines.append(
                f"- [{i.get('severity', 'medium')}] "
                f"{str(i.get('area', '')).replace('_', ' ')}: {i.get('note', '')}"
            )
    else:
        lines.append("- None recorded at gate.")
    return "\n".join(lines)


def _combine_packs(packs: dict[str, str]) -> str:
    parts = [packs[k] for k in PACK_BY_KEY if k in packs]
    return "\n\n---\n\n".join(parts)


def _teaser(markdown: str, *, limit: int = 1200) -> str:
    text = markdown.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("\n", 1)[0].rstrip()
    return f"{cut}\n\n…[full deliverable in Documents / Expand]"


# --- export formats (branded shell) ----------------------------------------


def export_docx(markdown: str, meta: ExportMeta) -> bytes:
    return export_branded_docx(markdown, meta)


def export_pdf(markdown: str, meta: ExportMeta) -> bytes:
    return export_branded_pdf(markdown, meta)


def export_markdown(markdown: str, meta: ExportMeta) -> bytes:  # noqa: ARG001
    return markdown.encode("utf-8")


EXPORTERS = {
    "md": (export_markdown, "text/markdown", "md"),
    "docx": (
        export_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "pdf": (export_pdf, "application/pdf", "pdf"),
}
