"""Snapshot narrative + export formats (D60) and card correction endpoints."""

from fastapi.testclient import TestClient

PLANNING_ANSWERS = [
    "Patients miss clinic slots and staff waste hours rescheduling by phone.",
    "First version covers rescheduling only. Cancellations are out.",
    "Clinic managers own it. Front desk staff and patients use it daily.",
]
RISK_CONFIRM = "Yes, that's correct"


def _accepted_project(client: TestClient, email: str) -> tuple[str, str]:
    client.post("/auth/dev-session", json={"display_name": "Docs", "email": email})
    project_id = client.post(
        "/projects", json={"brief": "A clinic booking tool for patients"}
    ).json()["id"]
    client.get(f"/projects/{project_id}/messages")
    for answer in PLANNING_ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    client.post(f"/projects/{project_id}/gate", json={"action": "accept"})
    snapshot = client.get(f"/projects/{project_id}/snapshots").json()[0]
    return project_id, snapshot["id"]


def test_snapshot_carries_narrative(client: TestClient) -> None:
    project_id, _sid = _accepted_project(client, "narrative@example.com")
    snapshot = client.get(f"/projects/{project_id}/snapshots").json()[0]
    assert snapshot["narrative"]  # scripted narrative without a key
    assert snapshot["body"].startswith("# Project Charter")


def test_export_all_formats(client: TestClient) -> None:
    project_id, snapshot_id = _accepted_project(client, "export@example.com")
    base = f"/projects/{project_id}/snapshots/{snapshot_id}/export"

    md = client.get(f"{base}?format=md")
    assert md.status_code == 200
    assert "markdown" in md.headers["content-type"]

    docx = client.get(f"{base}?format=docx")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"  # zip container

    pdf = client.get(f"{base}?format=pdf")
    assert pdf.status_code == 200
    assert pdf.content[:5] == b"%PDF-"

    assert client.get(f"{base}?format=exe").status_code == 422


def test_card_edit_and_strike(client: TestClient) -> None:
    project_id, _sid = _accepted_project(client, "cardfix@example.com")
    cards = [c for c in client.get(f"/projects/{project_id}/cards").json() if c["kind"] != "source"]
    target = cards[0]

    edited = client.patch(
        f"/projects/{project_id}/cards/{target['id']}",
        json={"body": "Corrected fact body."},
    )
    assert edited.status_code == 200
    assert edited.json()["body"] == "Corrected fact body."
    assert edited.json()["version"] == target["version"] + 1

    struck = client.post(f"/projects/{project_id}/cards/{cards[1]['id']}/retire")
    assert struck.status_code == 204
    refreshed = {c["id"]: c for c in client.get(f"/projects/{project_id}/cards").json()}
    assert refreshed[cards[1]["id"]]["status"] == "retired"


def test_audit_trail_records_human_decisions(client: TestClient) -> None:
    project_id, _sid = _accepted_project(client, "audit@example.com")
    events = client.get(f"/projects/{project_id}/audit").json()
    kinds = [e["kind"] for e in events]
    assert "project_created" in kinds
    assert "area_answered" in kinds
    assert "gate_accepted" in kinds
    assert all(e["actor"] == "Docs" for e in events)
    # Newest first
    assert kinds[0] == "gate_accepted"
    answered = next(e for e in events if e["kind"] == "area_answered")
    assert answered["detail"].get("area")
    assert answered["detail"].get("snippet")

    cards = client.get(f"/projects/{project_id}/cards").json()
    fact = next(c for c in cards if c["kind"] != "source")
    client.post(f"/projects/{project_id}/cards/{fact['id']}/retire")
    kinds = [e["kind"] for e in client.get(f"/projects/{project_id}/audit").json()]
    assert kinds[0] == "card_struck"


def test_auto_feasibility_runs_before_planning_gate(client: TestClient) -> None:
    project_id, _sid = _accepted_project(client, "autofeas@example.com")
    thread = client.get(
        f"/projects/{project_id}/messages", params={"phase": "planning"}
    ).json()
    reports = [
        m for m in thread
        if m.get("widget") and m["widget"].get("type") == "feasibility_report"
    ]
    assert len(reports) == 1  # ran exactly once, unprompted
    # And the Charter narrative carries the feasibility input (scripted echo).
    snapshot = client.get(f"/projects/{project_id}/snapshots").json()[0]
    assert snapshot["narrative"]


def test_srs_narrative_has_structured_sections(client: TestClient) -> None:
    project_id, _sid = _accepted_project(client, "srs@example.com")
    # Drive Requirements: answer all nine areas, then pick packs + accept.
    for _ in range(9):
        client.post(
            f"/projects/{project_id}/messages",
            json={"content": "The system shall handle the stated task for this area."},
        )
    thread = client.get(f"/projects/{project_id}/messages").json()
    picker = next(
        (
            m["widget"]
            for m in reversed(thread)
            if m.get("widget") and m["widget"].get("type") == "deliverable_picker"
        ),
        None,
    )
    assert picker is not None
    assert len(picker["packs"]) == 10

    generated = client.post(
        f"/projects/{project_id}/gate",
        json={
            "action": "select_packs",
            "pack_ids": [
                "epics_features_stories",
                "traceability_matrix",
                "quality_gap_report",
            ],
            "pack_mode": "separate",
        },
    )
    assert generated.status_code == 200
    panel = next(
        (
            m["widget"]
            for m in reversed(generated.json())
            if m.get("widget") and m["widget"].get("type") == "acceptance_panel"
        ),
        None,
    )
    assert panel is not None
    assert panel.get("selected_packs")
    assert panel.get("full_digest")
    assert panel.get("pack_mode") == "separate"
    assert "full deliverable" not in (panel.get("full_digest") or "")
    assert len(panel["full_digest"]) >= len(panel.get("digest") or "")

    accepted = client.post(f"/projects/{project_id}/gate", json={"action": "accept"})
    assert accepted.status_code == 200
    snapshots = client.get(f"/projects/{project_id}/snapshots").json()
    srs = next(s for s in snapshots if s["phase"] == "requirements")
    narrative = srs["narrative"]
    assert srs["document"] == "Requirements deliverables"
    assert srs["narratives"] is not None
    assert srs["narratives"]["mode"] == "separate"
    assert "epics_features_stories" in srs["narratives"]["packs"]
    assert "# User Story:" in narrative or "Epic:" in narrative
    assert "REQ-" in narrative or "Traceability" in narrative or "Scores" in narrative
    assert "**What**" in narrative
    assert "pack_generation_failed" not in narrative
    assert panel.get("failed_packs") in (None, [])
