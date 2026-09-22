"""Cards/strings/snapshots (D17, D22). Sole writer path for the knowledge model.

Called from two places: CardKnowledge (the graph's storage backend, via
KnowledgePort) and runner.py's on_accept (gate-time promotion + snapshot).
Nothing here talks to the graph - it only knows about cards/strings/projects.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.templates import PhaseTemplate
from app.models.card import Card
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.models.string import CardString
from app.services import belief as belief_service
from app.services.belief import RETIRED, SOURCE_KIND, SUPPORTED_BY

ACCEPTED = "accepted"


def record_facts(
    session: Session,
    project: Project,
    *,
    area: str,
    facts: list[str],
    source_message_id: str,
) -> tuple[list[Card], list[tuple[Card, str, dict | None]]]:
    """Insert facts through the belief layer (duplicate/conflict aware).

    Conflicts are judged by meaning BEFORE dedupe - similarity cannot tell a
    rewording from a one-word meaning flip (E2E finding).
    """
    if not facts:
        return [], []
    conflicted = belief_service.scan_conflicts(session, project, area, facts)
    created: list[Card] = []
    outcomes: list[tuple[Card, str, dict | None]] = []
    for index, fact in enumerate(facts):
        other = conflicted.get(index)
        if other is not None:
            card, meta = belief_service.add_conflicting_fact(
                session, project, area=area, fact=fact,
                source_ref=source_message_id, other=other,
            )
            created.append(card)
            outcomes.append((card, "conflict", meta))
            continue
        card, outcome, meta = belief_service.assimilate_fact(
            session,
            project,
            area=area,
            fact=fact,
            source_ref=source_message_id,
        )
        created.append(card)
        outcomes.append((card, outcome, meta))
    return created, outcomes


def conflict_card_widget(
    *,
    conflict_id: str,
    card: Card,
    other_card_id: str,
    other_body: str,
) -> dict[str, Any]:
    return {
        "type": "conflict_card",
        "conflict_id": conflict_id,
        "card_a_id": str(card.id),
        "card_b_id": other_card_id,
        "statement_a": card.body,
        "statement_b": other_body,
    }


def conflict_card_widget_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "conflict_card",
        "conflict_id": str(row["id"]),
        "card_a_id": str(row["card_a"]["id"]),
        "card_b_id": str(row["card_b"]["id"]),
        "statement_a": str(row["card_a"]["body"]),
        "statement_b": str(row["card_b"]["body"]),
    }


def list_cards(session: Session, project: Project) -> list[Card]:
    return list(
        session.scalars(
            select(Card).where(Card.project_id == project.id).order_by(Card.created_at.desc())
        ).all()
    )


def list_snapshots(session: Session, project: Project) -> list[Snapshot]:
    return list(
        session.scalars(
            select(Snapshot)
            .where(Snapshot.project_id == project.id)
            .order_by(Snapshot.created_at.asc())
        ).all()
    )


def requirements_stale_since(session: Session, project: Project):
    """Latest Planning accept timestamp, if it postdates the latest
    Requirements accept - a coarse, document-level staleness signal (D89).

    Not a card-content check: render_snapshot() already resolves pointers
    against live card rows, so a Planning edit is visible to any re-render
    immediately - no plumbing needed there. What actually goes stale is the
    *already-generated* Requirements deliverable (a frozen Snapshot.narrative
    string, an exported OneDrive file), which does not regenerate on its own.
    Returns None when nothing is stale: no Planning accept, Requirements has
    never been drafted yet (found live - a brand-new project moving from
    Planning's first accept straight into its first Requirements interview
    is not "stale," there is nothing yet for it to be stale against), or
    Requirements was drafted/redrafted after the last Planning accept."""
    snaps = list_snapshots(session, project)
    last_planning = next((s.created_at for s in reversed(snaps) if s.phase == "planning"), None)
    last_requirements = next(
        (s.created_at for s in reversed(snaps) if s.phase == "requirements"), None
    )
    if last_planning is None or last_requirements is None:
        return None
    # >= not >: a tied timestamp (same-second accepts, e.g. under low-res
    # storage precision) should read as stale, not silently hidden - a false
    # "stale" just shows a dismissible banner; a false "not stale" hides a
    # possibly-real change entirely.
    if last_planning >= last_requirements:
        return last_planning
    return None


def render_snapshot(session: Session, snapshot: Snapshot) -> str:
    """Deterministic document body from snapshot pointers. No LLM (D17)."""
    from app.agents.templates import get_template

    template = get_template(snapshot.phase)
    ids: list[UUID] = []
    for pointer in snapshot.card_versions:
        try:
            ids.append(UUID(str(pointer["card_id"])))
        except (KeyError, ValueError):
            continue
    cards_by_id = {
        c.id: c
        for c in session.scalars(select(Card).where(Card.id.in_(ids))).all()
    } if ids else {}
    grouped: dict[str, list[str]] = {a.key: [] for a in template.areas}
    extras: list[str] = []
    for pointer in snapshot.card_versions:
        try:
            card = cards_by_id.get(UUID(str(pointer["card_id"])))
        except ValueError:
            continue
        if card is None or card.kind == SOURCE_KIND:
            continue
        line = card.body.strip()
        if not line:
            continue
        if card.coverage_area in grouped:
            grouped[card.coverage_area].append(line)
        else:
            extras.append(line)

    lines = [f"# {template.document}", ""]
    for area in template.areas:
        facts = grouped[area.key]
        if not facts:
            continue
        lines.append(f"## {area.label}")
        lines.extend(f"- {fact}" for fact in facts)
        lines.append("")
    if extras:
        lines.append("## Other")
        lines.extend(f"- {fact}" for fact in extras)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def digest_lines(session: Session, project: Project) -> list[str]:
    """Everything known, as '[area] fact (from: source)' lines, for the graph's
    read-back/aside/turn prompts - human source names let the model cite
    'from kickoff-notes.md' instead of internal labels."""
    sources = card_sources(session, project)
    cards = session.scalars(
        select(Card)
        .where(
            Card.project_id == project.id,
            Card.kind != SOURCE_KIND,
            Card.status != RETIRED,
        )
        .order_by(Card.created_at.asc())
    ).all()
    lines = []
    for c in cards:
        labels = sources.get(c.id)
        origin = f" (from: {', '.join(labels)})" if labels else ""
        lines.append(f"[{c.coverage_area or 'general'}] {c.body}{origin}")
    return lines


def area_facts(session: Session, project: Project, area: str) -> list[str]:
    """Live fact bodies for one coverage area, oldest first."""
    cards = session.scalars(
        select(Card)
        .where(
            Card.project_id == project.id,
            Card.coverage_area == area,
            Card.kind != SOURCE_KIND,
            Card.status != RETIRED,
        )
        .order_by(Card.created_at.asc())
    ).all()
    return [c.body for c in cards]


def update_card(session: Session, project: Project, card_id: UUID, body: str) -> Card:
    """Human correction of a fact (D22 status flow stays; version bumps)."""
    card = session.get(Card, card_id)
    if card is None or card.project_id != project.id or card.kind == SOURCE_KIND:
        raise ValueError("card not found")
    card.body = body.strip()
    card.version += 1
    # Re-embed immediately (D65 polish) - leaving this None dropped edited
    # cards out of vector retrieval/dedupe until something else happened to
    # touch them again, which nothing reliably did.
    card.embedding = belief_service.embed_fact(card.body)
    session.commit()
    session.refresh(card)
    return card


def retire_card(session: Session, project: Project, card_id: UUID) -> None:
    """Human strike-through: the card leaves digests and future snapshots."""
    card = session.get(Card, card_id)
    if card is None or card.project_id != project.id or card.kind == SOURCE_KIND:
        raise ValueError("card not found")
    card.status = RETIRED
    session.commit()


def card_sources(session: Session, project: Project) -> dict[UUID, list[str]]:
    """card_id -> human-readable source labels (chat message or upload filename)."""
    from app.models.upload import Upload

    rows = session.scalars(
        select(CardString).where(
            CardString.project_id == project.id, CardString.kind == SUPPORTED_BY
        )
    ).all()
    source_ids = {r.to_card_id for r in rows}
    sources = {
        c.id: c.body
        for c in session.scalars(select(Card).where(Card.id.in_(source_ids))).all()
    } if source_ids else {}
    upload_names: dict[str, str] = {}
    for upload in session.scalars(
        select(Upload).where(Upload.project_id == project.id)
    ).all():
        upload_names[f"upload:{upload.id}"] = upload.filename
    out: dict[UUID, list[str]] = {}
    for row in rows:
        ref = sources.get(row.to_card_id, "")
        if ref.startswith("upload:"):
            label = upload_names.get(ref, "upload")
        elif ref.startswith("feasibility:"):
            label = "feasibility research"
        elif ref == "brief":
            label = "project brief"
        else:
            label = "chat"
        labels = out.setdefault(row.from_card_id, [])
        if label not in labels:
            labels.append(label)
    return out


def freeze_snapshot(
    session: Session, project: Project, template: PhaseTemplate, account_id: UUID
) -> Snapshot:
    """Promote this phase's cards to accepted and freeze a pointer snapshot over them.

    Scoped by the template's own coverage-area keys - Planning's and
    Requirements' area-key sets don't overlap, so this is exact for every
    named area. "general" cards (post-revise listening, area=None in the
    graph) carry no phase marker and are intentionally excluded here -
    documented in DECISIONS.md (D52) rather than guessed at.

    Two separate queries, not one (D89): a *second* accept of the same phase
    (a targeted Planning redraft touching only one area, say) must still
    produce a complete, self-contained snapshot. Cards from an untouched area
    are already status=accepted from the first accept, so a single query
    filtered to "not yet accepted" would promote nothing for them AND leave
    them out of this snapshot's pointers - the rendered document would be
    missing every section except the one just redrafted. Promotion stays
    scoped to the not-yet-accepted delta; pointers are built from every
    current, non-retired card in the template's areas, regardless of status.
    """
    area_keys = [a.key for a in template.areas]
    to_promote = session.scalars(
        select(Card).where(
            Card.project_id == project.id,
            Card.coverage_area.in_(area_keys),
            Card.status.notin_([ACCEPTED, RETIRED]),
        )
    ).all()
    for card in to_promote:
        card.status = ACCEPTED

    all_area_cards = session.scalars(
        select(Card).where(
            Card.project_id == project.id,
            Card.coverage_area.in_(area_keys),
            Card.status != RETIRED,
        )
    ).all()
    pointers = [{"card_id": str(card.id), "version": card.version} for card in all_area_cards]

    if all_area_cards:
        card_ids = [c.id for c in all_area_cards]
        source_ids = set(
            session.scalars(
                select(CardString.to_card_id).where(
                    CardString.kind == SUPPORTED_BY, CardString.from_card_id.in_(card_ids)
                )
            ).all()
        )
        for source_id in source_ids:
            source = session.get(Card, source_id)
            if source is not None:
                pointers.append({"card_id": str(source.id), "version": source.version})

    snapshot = Snapshot(
        project_id=project.id,
        phase=template.key,
        card_versions=pointers,
        accepted_by_account_id=account_id,
    )
    session.add(snapshot)
    session.commit()
    return snapshot
