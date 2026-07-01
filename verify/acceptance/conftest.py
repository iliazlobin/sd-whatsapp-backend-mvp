"""Shared fixtures and helpers for the WhatsApp MVP black-box acceptance suite.

These tests do NOT import `src.whatsapp`. They talk to the running system
via HTTP/WebSocket at API_BASE_URL. Test isolation is achieved through
unique user_ids per test — no database clearing required.
"""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url():
    return API_BASE_URL


@pytest.fixture(scope="session")
def client(base_url):
    """Session-scoped httpx client for the entire acceptance run."""
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture
def fresh_user_id():
    """Unique user_id per test to ensure isolation."""
    return str(uuid.uuid4())


@pytest.fixture
def fresh_msg_id():
    """Unique client_msg_id per test for message dedup testing."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_200(r, expected_status=200):
    """Assert status and return parsed JSON."""
    assert (
        r.status_code == expected_status
    ), f"Expected {expected_status}, got {r.status_code}: {r.text}"
    return r.json()


def assert_201(r):
    return assert_200(r, 201)


def assert_403(r):
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    return r.json()


def assert_404(r):
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    return r.json()


def assert_422(r):
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    return r.json()


def assert_409(r):
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Setup helpers — create users, chats, and messages via HTTP
# ---------------------------------------------------------------------------


def create_user(client, username=None, display_name=None):
    """Create a user and return the parsed response body (201)."""
    if username is None:
        username = f"user-{uuid.uuid4().hex[:12]}"
    if display_name is None:
        display_name = username.capitalize()
    r = client.post(
        "/v1/users",
        json={
            "username": username,
            "display_name": display_name,
        },
    )
    return assert_201(r)


def create_direct_chat(client, user_a, user_b):
    """Create a direct chat between two users. Returns parsed response body."""
    r = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [user_a, user_b],
            "created_by": user_a,
        },
    )
    body = r.json()
    # 201 for new, 200 for duplicate — both are valid
    assert r.status_code in (200, 201), f"Expected 200 or 201, got {r.status_code}: {r.text}"
    return body


def create_group_chat(client, name, member_ids, created_by):
    """Create a group chat. Returns parsed response body (201)."""
    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": name,
            "member_ids": member_ids,
            "created_by": created_by,
        },
    )
    return assert_201(r)


def send_message(client, chat_id, sender_id, content="Hello", client_msg_id=None):
    """Send a message to a chat. Returns parsed response body (201)."""
    if client_msg_id is None:
        client_msg_id = str(uuid.uuid4())
    r = client.post(
        "/v1/messages",
        json={
            "chat_id": chat_id,
            "sender_id": sender_id,
            "content": content,
            "client_msg_id": client_msg_id,
        },
    )
    return assert_201(r)


def ack_message(client, message_id, user_id, status="delivered"):
    """Acknowledge a message. Returns parsed response body."""
    r = client.post(
        f"/v1/messages/{message_id}/ack",
        json={
            "user_id": user_id,
            "status": status,
        },
    )
    return assert_200(r)


def get_inbox(client, user_id, since=0, limit=50):
    """Sync inbox for a user. Returns parsed response body."""
    r = client.get(
        "/v1/inbox",
        params={
            "user_id": user_id,
            "since": since,
            "limit": limit,
        },
    )
    return assert_200(r)


def get_chat_history(client, chat_id, user_id, limit=20, before=None):
    """Get paginated chat history. Returns parsed response body."""
    params = {"user_id": user_id, "limit": limit}
    if before is not None:
        params["before"] = before
    r = client.get(f"/v1/chats/{chat_id}/messages", params=params)
    return assert_200(r)
