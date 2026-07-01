"""FR-4: Create a group chat.

POST /v1/chats {type: "group", name, member_ids, created_by}
→ 201 {chat_id, type, name, member_count, created_at}
Empty name → 422. >256 members → 422.
created_by is auto-added as admin.
"""

from verify.acceptance.conftest import (
    assert_201,
    assert_422,
    create_user,
)


def test_create_group_chat_success(client):
    """Create a group chat → 201."""
    alice = create_user(client, "alice-fr4")["user_id"]
    bob = create_user(client, "bob-fr4")["user_id"]
    charlie = create_user(client, "charlie-fr4")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "Study Group",
            "member_ids": [alice, bob, charlie],
            "created_by": alice,
        },
    )
    body = assert_201(r)

    assert "chat_id" in body
    assert body["type"] == "group"
    assert body["name"] == "Study Group"
    assert body["member_count"] == 3
    assert "created_at" in body


def test_create_group_chat_minimal_size(client):
    """Group chat with exactly 2 members → 201 (creator + 1)."""
    alice = create_user(client, "alice-fr4-min")["user_id"]
    bob = create_user(client, "bob-fr4-min")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "Duo Group",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    body = assert_201(r)
    assert body["member_count"] == 2


def test_create_group_chat_empty_name_422(client):
    """Empty or missing name → 422."""
    alice = create_user(client, "alice-fr4-en")["user_id"]
    bob = create_user(client, "bob-fr4-en")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert_422(r)

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert_422(r)


def test_create_group_chat_too_few_members_422(client):
    """Group with 1 member → 422."""
    alice = create_user(client, "alice-fr4-1m")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "Solo Group",
            "member_ids": [alice],
            "created_by": alice,
        },
    )
    assert_422(r)


def test_create_group_chat_created_by_not_in_members_422(client):
    """created_by must be in member_ids → 422."""
    alice = create_user(client, "alice-fr4-cb")["user_id"]
    bob = create_user(client, "bob-fr4-cb")["user_id"]

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "Test",
            "member_ids": [bob],
            "created_by": alice,
        },
    )
    assert_422(r)


def test_create_group_chat_too_many_members_422(client):
    """>256 members → 422. Tests boundary by sending 257 member IDs."""
    alice = create_user(client, "alice-fr4-many")["user_id"]

    # Create 257 unique user IDs (we won't register them all,
    # but the endpoint should validate count before checking existence)
    member_ids = [alice] + [f"00000000-0000-0000-0000-{i:012d}" for i in range(256)]

    r = client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "Massive Group",
            "member_ids": member_ids,
            "created_by": alice,
        },
    )
    assert_422(r)
