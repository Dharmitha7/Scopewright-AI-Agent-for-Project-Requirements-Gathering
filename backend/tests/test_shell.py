from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dev_session_and_create_project(client: TestClient) -> None:
    denied = client.get("/projects")
    assert denied.status_code == 401

    signed = client.post(
        "/auth/dev-session",
        json={"display_name": "Rahul", "email": "rahul@example.com"},
    )
    assert signed.status_code == 200
    assert signed.json()["display_name"] == "Rahul"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "rahul@example.com"

    empty = client.get("/projects")
    assert empty.status_code == 200
    assert empty.json() == []

    created = client.post(
        "/projects",
        json={"brief": "A clinic booking tool for patients to reschedule visits"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"].startswith("A clinic booking tool")
    listed = client.get("/projects")
    assert len(listed.json()) == 1


def test_blank_brief_rejected(client: TestClient) -> None:
    client.post(
        "/auth/dev-session",
        json={"display_name": "Rahul", "email": "rahul@example.com"},
    )
    response = client.post("/projects", json={"brief": "  "})
    assert response.status_code == 422


def test_project_routes_guardrails(client: TestClient) -> None:
    client.post(
        "/auth/dev-session",
        json={"display_name": "Rahul", "email": "chat@example.com"},
    )
    created = client.post(
        "/projects",
        json={"brief": "A clinic booking tool for patients to reschedule visits"},
    )
    project_id = created.json()["id"]

    one = client.get(f"/projects/{project_id}")
    assert one.status_code == 200
    assert one.json()["id"] == project_id
    assert one.json()["phase"] == "planning"

    renamed = client.patch(f"/projects/{project_id}", json={"name": "Clinic Booking"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Clinic Booking"
    assert client.get(f"/projects/{project_id}").json()["name"] == "Clinic Booking"
    assert client.get("/projects").json()[0]["name"] == "Clinic Booking"

    blank_name = client.patch(f"/projects/{project_id}", json={"name": "   "})
    assert blank_name.status_code == 422

    missing = client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404

    blank = client.post(f"/projects/{project_id}/messages", json={"content": "  "})
    assert blank.status_code == 422

    deleted = client.delete(f"/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/projects/{project_id}").status_code == 404
    assert client.get("/projects").json() == []


def test_logout_clears_session(client: TestClient) -> None:
    client.post(
        "/auth/dev-session",
        json={"display_name": "Rahul", "email": "logout@example.com"},
    )
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert client.get("/projects").status_code == 401


def test_junk_cookie_is_unauthorized(client: TestClient) -> None:
    client.cookies.set("crewlane_session", "not-a-jwt")
    assert client.get("/auth/me").status_code == 401


def test_create_with_name_and_brief_mining(client: TestClient) -> None:
    client.post(
        "/auth/dev-session",
        json={"display_name": "Yash", "email": "frontdoor@example.com"},
    )
    created = client.post(
        "/projects",
        json={
            "brief": "Members book gym classes online. Trainers manage schedules.",
            "name": "Gym Portal",
        },
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Gym Portal"

    # The brief was mined into cards before the interview opened.
    cards = client.get(f"/projects/{created.json()['id']}/cards").json()
    mined = [c for c in cards if "project brief" in c["sources"]]
    assert len(mined) >= 1
