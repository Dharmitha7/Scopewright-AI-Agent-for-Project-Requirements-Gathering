from uuid import UUID

from app.models.account import Account
from app.models.project import Project
from app.services import belief as belief_service
from app.services import feasibility as feasibility_service


def _planning_project(db_session, email: str):
    account = Account(email=email, display_name="Feas")
    db_session.add(account)
    db_session.commit()
    project = Project(
        name="Feas test",
        brief="Build a mobile banking app",
        phase="planning",
        created_by_account_id=account.id,
    )
    db_session.add(project)
    db_session.commit()
    return project


def test_feasibility_during_planning(db_session):
    project = _planning_project(db_session, "feas1@example.com")
    message = feasibility_service.run_feasibility(
        db_session, project, "mobile banking app market size"
    )
    assert message.widget["type"] == "feasibility_report"
    assert message.widget["sources"]


def test_resolve_conflict(db_session):
    project = _planning_project(db_session, "conflict-resolve@example.com")
    _first, _, _meta = belief_service.assimilate_fact(
        db_session,
        project,
        area="scope",
        fact="Scope includes mobile apps",
        source_ref="msg:1",
    )
    second, outcome, meta2 = belief_service.assimilate_fact(
        db_session,
        project,
        area="scope",
        fact="Scope excludes mobile apps",
        source_ref="msg:2",
    )
    if outcome != "conflict" or not meta2:
        return
    belief_service.resolve_conflict(
        db_session,
        project,
        UUID(meta2["conflict_id"]),
        second.id,
    )
    assert belief_service.list_conflicts(db_session, project) == []
