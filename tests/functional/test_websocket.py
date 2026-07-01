"""Functional tests for WebSocket endpoint.

Uses Starlette TestClient (sync) — ASGITransport (httpx 0.28) hangs on
co-located WebSocket + HTTP routes on the same path.
"""

import uuid

from starlette.testclient import TestClient


def test_ws_no_user_id(app):
    """GET /v1/ws without user_id → 403."""
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/v1/ws")
    assert r.status_code == 403


def test_ws_fake_user_id(app):
    """GET /v1/ws with non-existent user_id → 404."""
    client = TestClient(app, raise_server_exceptions=False)
    fake_id = str(uuid.uuid4())
    r = client.get("/v1/ws", params={"user_id": fake_id})
    assert r.status_code == 404


def test_websocket_connect_and_receive(app):
    """Connect via WebSocket and verify connected message is received."""
    client = TestClient(app, raise_server_exceptions=False)

    # Create a user first
    r = client.post(
        "/v1/users",
        json={
            "username": "ws-test-user",
            "display_name": "WS User",
        },
    )
    assert r.status_code == 201
    user_id = r.json()["user_id"]

    # Connect via WebSocket
    with client.websocket_connect(f"/v1/ws?user_id={user_id}") as ws:
        data = ws.receive_json()
        assert data["type"] == "connected"
        assert data["user_id"] == user_id
