"""Message phase / thread filtering for Planning and Requirements tabs."""

from fastapi.testclient import TestClient

ANSWERS = [
    "Patients miss clinic slots and staff waste hours rescheduling by phone.",
    "First version covers rescheduling only. Cancellations are out.",
    "Clinic managers own it. Front desk staff and patients use it daily.",
]
RISK_CONFIRM = "Yes, that's correct"


def _project(client: TestClient, email: str) -> str:
    client.post("/auth/dev-session", json={"display_name": "Tabs", "email": email})
    created = client.post(
        "/projects",
        json={"brief": "A clinic booking tool for patients to reschedule visits"},
    )
    assert created.status_code == 201
    return created.json()["id"]


def _last_widget(messages: list[dict], kind: str) -> dict | None:
    for message in reversed(messages):
        if message.get("widget") and message["widget"].get("type") == kind:
            return message["widget"]
    return None


def test_messages_stamped_and_filtered(client: TestClient) -> None:
    project_id = _project(client, "phase-stamp@example.com")
    thread = client.get(f"/projects/{project_id}/messages").json()
    assert thread
    assert all(m["phase"] == "planning" for m in thread)
    assert all(":planning" in m["thread_key"] for m in thread)

    req = client.get(
        f"/projects/{project_id}/messages", params={"phase": "requirements"}
    ).json()
    assert req == []


def test_wrong_tab_post_rejected(client: TestClient) -> None:
    project_id = _project(client, "wrong-tab@example.com")
    client.get(f"/projects/{project_id}/messages")
    res = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "hello", "tab": "requirements"},
    )
    assert res.status_code == 422
    assert "locked" in res.json()["detail"].lower()


def test_accept_isolates_threads(client: TestClient) -> None:
    project_id = _project(client, "accept-tabs@example.com")
    client.get(f"/projects/{project_id}/messages")
    for answer in ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})

    accepted = client.post(
        f"/projects/{project_id}/gate",
        json={"action": "accept", "tab": "planning"},
    )
    assert accepted.status_code == 200
    planning_thread = accepted.json()
    assert all(m["phase"] == "planning" for m in planning_thread)
    assert _last_widget(planning_thread, "gate_accepted") is not None
    assert _last_widget(planning_thread, "question_card") is None or (
        _last_widget(planning_thread, "question_card") or {}
    ).get("purpose") != "product_boundary"

    planning_get = client.get(
        f"/projects/{project_id}/messages", params={"phase": "planning"}
    ).json()
    assert all(m["phase"] == "planning" for m in planning_get)
    assert not any(
        (m.get("widget") or {}).get("purpose") == "product_boundary" for m in planning_get
    )

    requirements = client.get(
        f"/projects/{project_id}/messages", params={"phase": "requirements"}
    ).json()
    assert requirements
    assert all(m["phase"] == "requirements" for m in requirements)
    q = _last_widget(requirements, "question_card")
    assert q is not None
    assert q["purpose"] == "product_boundary"

    default = client.get(f"/projects/{project_id}/messages").json()
    assert all(m["phase"] == "requirements" for m in default)


def test_chat_state_writable_rules(client: TestClient) -> None:
    project_id = _project(client, "chat-state@example.com")
    planning = client.get(
        f"/projects/{project_id}/chat-state", params={"tab": "planning"}
    ).json()
    assert planning["writable"] is True
    assert planning["tab"] == "planning"

    req = client.get(
        f"/projects/{project_id}/chat-state", params={"tab": "requirements"}
    ).json()
    assert req["writable"] is False

    client.get(f"/projects/{project_id}/messages")
    for answer in ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    client.post(f"/projects/{project_id}/gate", json={"action": "accept"})

    after = client.get(
        f"/projects/{project_id}/chat-state", params={"tab": "planning"}
    ).json()
    assert after["writable"] is False
    live = client.get(
        f"/projects/{project_id}/chat-state", params={"tab": "requirements"}
    ).json()
    assert live["writable"] is True


def test_planning_post_locked_after_accept(client: TestClient) -> None:
    project_id = _project(client, "lock-planning@example.com")
    client.get(f"/projects/{project_id}/messages")
    for answer in ANSWERS:
        client.post(f"/projects/{project_id}/messages", json={"content": answer})
    client.post(f"/projects/{project_id}/messages", json={"content": RISK_CONFIRM})
    client.post(f"/projects/{project_id}/gate", json={"action": "accept"})

    res = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "change the charter", "tab": "planning"},
    )
    assert res.status_code == 422
