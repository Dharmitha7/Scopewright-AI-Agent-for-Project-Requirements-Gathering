from uuid import UUID

from sqlalchemy import select

from app.models.account import Account
from app.models.card import Card
from app.models.project import Project
from app.services import belief as belief_service
from app.services.belief import CONFIRMED
from app.services.cards import record_facts


def _project_with_account(db_session, email: str):
    account = Account(email=email, display_name="Belief")
    db_session.add(account)
    db_session.commit()
    project = Project(
        name="Belief test",
        brief="Test belief layer",
        phase="planning",
        created_by_account_id=account.id,
    )
    db_session.add(project)
    db_session.commit()
    return project, account


def test_duplicate_fact_becomes_confirmed(db_session):
    project, _account = _project_with_account(db_session, "dup@example.com")
    fact = "The primary stakeholder is the CFO"
    record_facts(db_session, project, area="stakeholders", facts=[fact], source_message_id="msg:1")
    record_facts(
        db_session,
        project,
        area="stakeholders",
        facts=["Primary stakeholder is the CFO"],
        source_message_id="msg:2",
    )
    cards = db_session.scalars(select(Card).where(Card.project_id == project.id)).all()
    fact_cards = [c for c in cards if c.kind != "source"]
    assert len(fact_cards) == 1
    assert fact_cards[0].status == CONFIRMED


def test_conflict_scan_flags_contradiction_by_meaning(db_session):
    """Conflicts come from the per-area meaning scan, never from similarity."""
    project, _account = _project_with_account(db_session, "conflict@example.com")
    (first_cards, _) = record_facts(
        db_session, project, area="scope",
        facts=["Scope includes mobile apps"], source_message_id="msg:a",
    )
    _, outcomes = record_facts(
        db_session, project, area="scope",
        facts=["Scope excludes mobile apps"], source_message_id="msg:b",
    )
    conflict_metas = [meta for _c, outcome, meta in outcomes if outcome == "conflict"]
    assert len(conflict_metas) == 1
    conflicts = belief_service.list_conflicts(db_session, project)
    assert len(conflicts) == 1
    assert first_cards[0].id in {
        UUID(conflicts[0]["card_a"]["id"]),
        UUID(conflicts[0]["card_b"]["id"]),
    }


def test_duplicate_detection_uses_embeddings_when_available(db_session):
    """_best_match's embedding path (belief.py) - exercises the preserved
    Python fallback on sqlite; the pgvector SQL path (0009) needs real
    Postgres, covered separately in test_retrieval_pgvector.py."""
    project, _account = _project_with_account(db_session, "embed-dup@example.com")
    card, outcome, _meta = belief_service.assimilate_fact(
        db_session, project, area="scope", fact="Scope includes mobile apps",
        source_ref="msg:1", embedding=[1.0, 0.0, 0.0],
    )
    assert outcome == "new"

    # Different wording, but a near-identical vector (cosine ~0.9999) -
    # corroborates purely from the embedding, independent of text.
    match_card, match_outcome, _meta2 = belief_service.assimilate_fact(
        db_session, project, area="scope", fact="Totally different wording",
        source_ref="msg:2", embedding=[0.99, 0.01, 0.0],
    )
    assert match_outcome == "corroborated"
    assert match_card.id == card.id


def test_below_threshold_embedding_match_still_creates_new_card(db_session):
    """Pins the equivalence the pgvector SQL rewrite depends on: a match
    scoring below DUPLICATE_SIM is discarded either way, so pushing the
    threshold into the SQL WHERE clause changes nothing observable here."""
    project, _account = _project_with_account(db_session, "embed-new@example.com")
    card, outcome, _meta = belief_service.assimilate_fact(
        db_session, project, area="scope", fact="Scope includes mobile apps",
        source_ref="msg:1", embedding=[1.0, 0.0, 0.0],
    )
    assert outcome == "new"

    other, outcome2, _meta2 = belief_service.assimilate_fact(
        db_session, project, area="scope", fact="A related but different point",
        source_ref="msg:2", embedding=[0.5, 0.5, 0.0],  # cosine ~0.71, below 0.92
    )
    assert outcome2 == "new"
    assert other.id != card.id


def test_conflict_progress_counts_resolved(db_session):
    from app.services import belief as belief_service
    from app.services.cards import record_facts

    project, _account = _project_with_account(db_session, "progress@example.com")
    record_facts(
        db_session,
        project,
        area="scope",
        facts=["Scope includes mobile apps"],
        source_message_id="seed:a",
    )
    record_facts(
        db_session,
        project,
        area="scope",
        facts=["Scope excludes mobile apps"],
        source_message_id="seed:b",
    )
    progress = belief_service.conflict_progress(db_session, project)
    assert progress["total_count"] == 1
    assert progress["resolved_count"] == 0
    assert len(progress["items"]) == 1


def test_resolving_conflict_retires_loser(db_session):
    project, _account = _project_with_account(db_session, "retire@example.com")
    (first_cards, _) = record_facts(
        db_session, project, area="scope",
        facts=["Scope includes mobile apps"], source_message_id="m:1",
    )
    second_cards, outcomes = record_facts(
        db_session, project, area="scope",
        facts=["Scope excludes mobile apps"], source_message_id="m:2",
    )
    meta = next(meta for _c, outcome, meta in outcomes if outcome == "conflict")
    belief_service.resolve_conflict(
        db_session, project, UUID(meta["conflict_id"]), second_cards[0].id
    )
    db_session.refresh(first_cards[0])
    db_session.refresh(second_cards[0])
    assert second_cards[0].status == belief_service.CONFIRMED
    assert first_cards[0].status == belief_service.RETIRED


def test_paraphrase_guard_skips_same_polarity_near_duplicate(db_session, monkeypatch):
    """LLM may flag rewordings; same-polarity near-matches must not become conflicts."""
    project, _account = _project_with_account(db_session, "para@example.com")
    a = (
        "Managers will auto-approve PTO requests of five business days or fewer."
    )
    b = (
        "The system shall allow managers to auto-approve PTO requests that "
        "are under five business days."
    )
    assert belief_service.is_paraphrase(a, b)
    record_facts(db_session, project, area="scope", facts=[a], source_message_id="p:1")

    monkeypatch.setattr(
        belief_service,
        "complete_json",
        lambda *args, **kwargs: {"conflicts": [{"new": "N1", "existing": "E1"}]},
    )
    scanned = belief_service.scan_conflicts(db_session, project, "scope", [b])
    assert scanned == {}
    _, outcomes = record_facts(
        db_session, project, area="scope", facts=[b], source_message_id="p:2"
    )
    assert not any(outcome == "conflict" for _c, outcome, _m in outcomes)
    assert belief_service.list_conflicts(db_session, project) == []


def test_polarity_flip_still_conflicts_despite_high_similarity(db_session):
    assert (
        belief_service.is_paraphrase(
            "Scope includes mobile apps", "Scope excludes mobile apps"
        )
        is False
    )
    project, _account = _project_with_account(db_session, "flip@example.com")
    record_facts(
        db_session, project, area="scope",
        facts=["Scope includes mobile apps"], source_message_id="f:1",
    )
    _, outcomes = record_facts(
        db_session, project, area="scope",
        facts=["Scope excludes mobile apps"], source_message_id="f:2",
    )
    assert any(outcome == "conflict" for _c, outcome, _m in outcomes)


def test_resolve_cascades_siblings_sharing_winner(db_session):
    project, _account = _project_with_account(db_session, "cascade@example.com")
    shared, _, _ = belief_service.assimilate_fact(
        db_session, project, area="scope",
        fact="Managers may auto-approve PTO under five business days.",
        source_ref="c:shared",
    )
    challengers = [
        "HR must approve every PTO request.",
        "Managers may only recommend short PTO requests.",
        "Short PTO still requires HR sign-off.",
    ]
    metas = []
    for i, body in enumerate(challengers):
        _card, meta = belief_service.add_conflicting_fact(
            db_session, project, area="scope", fact=body,
            source_ref=f"c:{i}", other=shared,
        )
        metas.append(meta)
    assert len(belief_service.list_conflicts(db_session, project)) == 3
    cleared = belief_service.resolve_conflict(
        db_session, project, UUID(metas[0]["conflict_id"]), shared.id
    )
    assert cleared == 3
    assert belief_service.list_conflicts(db_session, project) == []
    db_session.refresh(shared)
    assert shared.status == belief_service.CONFIRMED
