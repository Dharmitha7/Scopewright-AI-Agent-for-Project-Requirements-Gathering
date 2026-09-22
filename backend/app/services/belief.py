"""Belief layer: duplicate corroboration and conflict detection (D13, D22)."""

from __future__ import annotations

import logging
import math
import re
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters.embeddings import get_embeddings
from app.agents.inference import PURPOSE_TAG, complete_json, get_inference
from app.core.config import get_settings
from app.models.audit_event import AuditEvent
from app.models.card import Card
from app.models.project import Project
from app.models.string import CardString

log = logging.getLogger(__name__)

CANDIDATE = "candidate"
CONFIRMED = "confirmed"
# A retired card lost a conflict or was struck by a human: it leaves the
# digest, retrieval, and snapshots, but stays in the DB for the audit trail.
RETIRED = "retired"
SUPPORTED_BY = "supported-by"
CONFLICTS_WITH = "conflicts-with"
SOURCE_KIND = "source"

DUPLICATE_SIM = 0.92
# Surface-near claims with the same polarity are paraphrases, not conflicts.
# Kept below includes/excludes (~0.92) pairs that flip meaning with one word.
PARAPHRASE_SIM = 0.65
# pgvector's cosine_distance() returns 1 - cosine_similarity, so a
# similarity floor translates to a distance ceiling this way round.
DUPLICATE_MAX_DISTANCE = 1 - DUPLICATE_SIM


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _negated(text: str) -> bool:
    """Cheap polarity cue so 'includes X' vs 'excludes X' stay conflicts."""
    t = f" {_normalize(text)} "
    return any(
        token in t
        for token in (
            " exclud",
            " not ",
            " no ",
            " never ",
            " cannot ",
            " can't ",
            " without ",
        )
    )


def is_paraphrase(a: str, b: str) -> bool:
    """True when wording is close and polarity matches — not a real conflict."""
    return _text_similarity(a, b) >= PARAPHRASE_SIM and _negated(a) == _negated(b)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    na = math.sqrt(math.sumprod(a, a))
    nb = math.sqrt(math.sumprod(b, b))
    if na == 0 or nb == 0:
        return 0.0
    return math.sumprod(a, b) / (na * nb)


def _supports_pgvector(session: Session) -> bool:
    """True once the session is bound to Postgres, where cards.embedding /
    evidence_chunks.embedding are real pgvector Vector columns (migration
    0009) - False on sqlite (tests), where they're plain JSON."""
    return session.get_bind().dialect.name == "postgresql"


def _sql_best_match(
    session: Session, project_id: UUID, embedding: list[float]
) -> tuple[Card | None, float]:
    """Indexed nearest-candidate lookup via the cards.embedding HNSW index -
    no full-table scan. Threshold pushed into SQL (WHERE distance <=
    DUPLICATE_MAX_DISTANCE) is safe: the one caller of _best_match already
    discards any match scoring below DUPLICATE_SIM regardless of what it
    was, so narrowing here changes nothing observable."""
    distance = Card.embedding.cosine_distance(embedding)
    row = session.execute(
        select(Card, distance.label("distance"))
        .where(
            Card.project_id == project_id,
            Card.kind != SOURCE_KIND,
            Card.status != RETIRED,
            Card.embedding.is_not(None),
            distance <= DUPLICATE_MAX_DISTANCE,
        )
        .order_by(distance)
        .limit(1)
    ).first()
    if row is None:
        return None, 0.0
    card, dist = row
    return card, 1 - dist


def _best_match(
    session: Session, project_id: UUID, fact: str, embedding: list[float] | None
) -> tuple[Card | None, float]:
    if embedding and _supports_pgvector(session):
        try:
            return _sql_best_match(session, project_id, embedding)
        except SQLAlchemyError:
            log.warning("pgvector dup lookup failed, falling back to full scan", exc_info=True)
            # clear the aborted-transaction state before the fallback queries run
            session.rollback()

    cards = session.scalars(
        select(Card).where(
            Card.project_id == project_id,
            Card.kind != SOURCE_KIND,
            Card.status != RETIRED,
        )
    ).all()
    best: Card | None = None
    best_score = 0.0
    for card in cards:
        if embedding and card.embedding:
            score = _cosine(embedding, card.embedding)
        else:
            score = _text_similarity(fact, card.body)
        if score > best_score:
            best, best_score = card, score
    return best, best_score


def embed_fact(text: str) -> list[float] | None:
    """Shared embed-one-string helper (used at insert time, on card edit,
    and for conflict-branch cards). A fact/card body is a document, not a
    query - embed_documents() applies EmbeddingGemma's document prompt
    (D70), not the query one retrieval.py uses."""
    settings = get_settings()
    return get_embeddings(settings).embed_documents([text])[0] or None


def _get_or_create_source(session: Session, project: Project, source_ref: str) -> Card:
    existing = session.scalar(
        select(Card).where(
            Card.project_id == project.id,
            Card.kind == SOURCE_KIND,
            Card.body == source_ref,
        )
    )
    if existing is not None:
        return existing
    card = Card(
        project_id=project.id,
        kind=SOURCE_KIND,
        coverage_area=None,
        body=source_ref,
        status=CANDIDATE,
    )
    session.add(card)
    session.flush()
    return card


def _link_supported_by(session: Session, project: Project, from_id: UUID, to_id: UUID) -> None:
    exists = session.scalar(
        select(CardString.id).where(
            CardString.kind == SUPPORTED_BY,
            CardString.from_card_id == from_id,
            CardString.to_card_id == to_id,
        )
    )
    if exists is None:
        session.add(
            CardString(
                project_id=project.id,
                kind=SUPPORTED_BY,
                from_card_id=from_id,
                to_card_id=to_id,
            )
        )


def assimilate_fact(
    session: Session,
    project: Project,
    *,
    area: str,
    fact: str,
    source_ref: str,
    embedding: list[float] | None = None,
) -> tuple[Card, str, dict | None]:
    """Returns (card, outcome, meta). meta is set on conflict (conflict_id, other_card_*)."""
    # Lazy: importing app.agents at module level is a circular import
    # (agents.__init__ -> runner -> knowledge -> cards -> belief).
    from app.agents.card_kinds import kind_for

    if embedding is None:
        embedding = embed_fact(fact)

    match, score = _best_match(session, project.id, fact, embedding)
    source = _get_or_create_source(session, project, source_ref)

    if match and score >= DUPLICATE_SIM:
        if match.status == CANDIDATE:
            match.status = CONFIRMED
        _link_supported_by(session, project, match.id, source.id)
        session.commit()
        return match, "corroborated", None

    # Conflict detection deliberately does NOT live here: a similarity
    # trigger produced false conflicts between complementary facts and
    # missed real contradictions with divergent wording (E2E finding).
    # scan_conflicts() judges by meaning per area instead.
    card = Card(
        project_id=project.id,
        kind=kind_for(project.phase, area),
        coverage_area=area,
        body=fact,
        status=CANDIDATE,
        embedding=embedding,
    )
    session.add(card)
    session.flush()
    _link_supported_by(session, project, card.id, source.id)
    session.commit()
    return card, "new", None


def scan_conflicts(
    session: Session, project: Project, area: str, texts: list[str]
) -> dict[int, Card]:
    """LLM meaning-check of incoming fact texts against the area's live facts.

    Runs BEFORE dedupe: 'includes X' vs 'excludes X' scores 0.92 on surface
    similarity, so a similarity-first pipeline merges the contradiction away.
    Returns {text_index: contradicted_existing_card}. One call per turn-area.
    """
    if not texts:
        return {}
    existing = session.scalars(
        select(Card).where(
            Card.project_id == project.id,
            Card.coverage_area == area,
            Card.kind != SOURCE_KIND,
            Card.status != RETIRED,
        )
    ).all()
    if not existing:
        return {}

    settings = get_settings()
    listing = (
        "EXISTING:\n"
        + "\n".join(f"E{i + 1}: {c.body}" for i, c in enumerate(existing))
        + "\nNEW:\n"
        + "\n".join(f"N{i + 1}: {t}" for i, t in enumerate(texts))
    )
    result = complete_json(
        get_inference(settings),
        model=settings.groq_model,
        system=(
            f"{PURPOSE_TAG} conflict_scan\n"
            "Compare the NEW statements against the EXISTING ones. Report a pair "
            "ONLY when they cannot both be true at once - a genuine contradiction "
            "in meaning. Rephrasings, complementary details, and different aspects "
            "of the same topic are NOT conflicts. "
            'Return {"conflicts": [{"new": "N1", "existing": "E2"}]} '
            "(empty list when nothing contradicts)."
        ),
        user=listing,
    )
    out: dict[int, Card] = {}
    for pair in result.get("conflicts") or []:
        try:
            new_index = int(str(pair.get("new", "")).lstrip("N")) - 1
            other = existing[int(str(pair.get("existing", "")).lstrip("E")) - 1]
        except (ValueError, IndexError):
            continue
        if 0 <= new_index < len(texts):
            # Drop LLM false positives: near-paraphrase with same polarity.
            if is_paraphrase(texts[new_index], other.body):
                continue
            out.setdefault(new_index, other)
    return out


def add_conflicting_fact(
    session: Session,
    project: Project,
    *,
    area: str,
    fact: str,
    source_ref: str,
    other: Card,
) -> tuple[Card, dict]:
    """Insert a fact that contradicts an existing card - never dedup-merged."""
    from app.agents.card_kinds import kind_for

    source = _get_or_create_source(session, project, source_ref)
    card = Card(
        project_id=project.id,
        kind=kind_for(project.phase, area),
        coverage_area=area,
        body=fact,
        status=CANDIDATE,
        embedding=embed_fact(fact),
    )
    session.add(card)
    session.flush()
    _link_supported_by(session, project, card.id, source.id)
    conflict = CardString(
        project_id=project.id,
        kind=CONFLICTS_WITH,
        from_card_id=card.id,
        to_card_id=other.id,
    )
    session.add(conflict)
    session.flush()
    meta = {
        "conflict_id": str(conflict.id),
        "other_card_id": str(other.id),
        "other_body": other.body,
    }
    session.commit()
    return card, meta


def resolve_conflict(
    session: Session, project: Project, conflict_id: UUID, winner_card_id: UUID
) -> int:
    """Resolve one conflict; cascade siblings that share the winner.

    Keeping W retires every other open opponent of W (same decision, many edges).
    Edges that only touch the loser are dropped without confirming the other side.
    Returns how many conflict edges were cleared (always >= 1 on success).
    """
    row = session.get(CardString, conflict_id)
    if row is None or row.project_id != project.id or row.kind != CONFLICTS_WITH:
        raise ValueError("conflict not found")
    if winner_card_id not in {row.from_card_id, row.to_card_id}:
        raise ValueError("winner must be one of the conflicting cards")
    winner = session.get(Card, winner_card_id)
    if winner is None:
        raise ValueError("winner card not found")
    loser_id = row.to_card_id if winner_card_id == row.from_card_id else row.from_card_id
    loser = session.get(Card, loser_id)
    if loser is not None:
        # E2E finding: leaving the loser as a live candidate let a contradicted
        # fact get promoted into the accepted Charter alongside its correction.
        loser.status = RETIRED
    winner.status = CONFIRMED
    session.delete(row)
    cleared = 1

    siblings = session.scalars(
        select(CardString).where(
            CardString.project_id == project.id,
            CardString.kind == CONFLICTS_WITH,
            CardString.id != conflict_id,
        )
    ).all()
    for edge in siblings:
        parties = {edge.from_card_id, edge.to_card_id}
        if winner_card_id in parties:
            other_id = edge.to_card_id if edge.from_card_id == winner_card_id else edge.from_card_id
            other = session.get(Card, other_id)
            if other is not None and other.status != RETIRED:
                other.status = RETIRED
            session.delete(edge)
            cleared += 1
        elif loser_id in parties:
            # Loser is gone; drop the edge, leave the other card as-is.
            session.delete(edge)
            cleared += 1

    session.commit()
    return cleared


def list_conflicts(session: Session, project: Project) -> list[dict]:
    rows = session.scalars(
        select(CardString).where(
            CardString.project_id == project.id,
            CardString.kind == CONFLICTS_WITH,
        )
    ).all()
    out: list[dict] = []
    for row in rows:
        a = session.get(Card, row.from_card_id)
        b = session.get(Card, row.to_card_id)
        if a is None or b is None:
            continue
        if a.status == RETIRED or b.status == RETIRED:
            continue
        out.append(
            {
                "id": str(row.id),
                "card_a": {"id": str(a.id), "body": a.body, "status": a.status},
                "card_b": {"id": str(b.id), "body": b.body, "status": b.status},
            }
        )
    return out


def count_resolved_conflicts(session: Session, project_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.project_id == project_id,
                AuditEvent.kind == "conflict_resolved",
            )
        )
        or 0
    )


def conflict_progress(session: Session, project: Project) -> dict:
    items = list_conflicts(session, project)
    resolved = count_resolved_conflicts(session, project.id)
    return {
        "items": items,
        "resolved_count": resolved,
        "total_count": len(items) + resolved,
    }
