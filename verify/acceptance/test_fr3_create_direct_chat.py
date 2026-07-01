"""FR-3: Create a direct (1:1) chat.

POST /v1/chats {type: "direct", member_ids: [u1, u2], created_by}
→ 201 {chat_id, type, member_count, created_at}
Duplicate → 200 with existing chat (idempotent).
Only one member → 422.
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_201,
    assert_422,
    create_user,
)


def test_create_direct_chat_success(client):
    """Create a direct chat between two users → 201."""
    alice = create_user(client, "alice-fr3")["user_id"]
    bob = create_user(client, "bob-fr3")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    body = assert_201(r)

    assert "chat_id" in body
    assert body["type"] == "direct"
    assert body["name"] is None
    assert body["member_count"] == 2
    assert "created_at" in body


def test_create_direct_chat_idempotent(client):
    """Creating the same direct chat twice returns 200 with existing chat."""
    alice = create_user(client, "alice-fr3-idem")["user_id"]
    bob = create_user(client, "bob-fr3-idem")["user_id"]

    # First request → 201
    r1 = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert_201(r1)
    chat1 = r1.json()

    # Second request (same users) → 200 idempotent
    r2 = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    body2 = assert_200(r2)
    assert body2["chat_id"] == chat1["chat_id"]


def test_create_direct_chat_reversed_order_idempotent(client):
    """Reversing member order is still idempotent (canonical ordering)."""
    alice = create_user(client, "alice-fr3-rev")["user_id"]
    bob = create_user(client, "bob-fr3-rev")["user_id"]

    r1 = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    body1 = assert_201(r1)

    # Reverse order → same chat
    r2 = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [bob, alice],
            "created_by": bob,
        },
    )
    body2 = assert_200(r2)
    assert body2["chat_id"] == body1["chat_id"]


def test_create_direct_chat_single_member_422(client):
    """Only one member → 422."""
    alice = create_user(client, "alice-fr3-single")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice],
            "created_by": alice,
        },
    )
    assert_422(r)


def test_create_direct_chat_three_members_422(client):
    """Three members for direct chat → 422."""
    alice = create_user(client, "alice-fr3-3m")["user_id"]
    bob = create_user(client, "bob-fr3-3m")["user_id"]
    charlie = create_user(client, "charlie-fr3-3m")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob, charlie],
            "created_by": alice,
        },
    )
    assert_422(r)


def test_create_direct_chat_created_by_not_in_members_422(client):
    """created_by must be in member_ids → 422 if not."""
    alice = create_user(client, "alice-fr3-cb")["user_id"]
    bob = create_user(client, "bob-fr3-cb")["user_id"]
    charlie = create_user(client, "charlie-fr3-cb")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": charlie,
        },
    )
    assert_422(r)
