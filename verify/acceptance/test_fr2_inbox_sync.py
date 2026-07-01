"""FR-2: Inbox sync (offline delivery).

GET /v1/inbox?user_id=<uuid>&since=<global_seq>&limit=<n>
→ 200 {messages: [...], next_cursor: <seq>}
Empty inbox → 200 {messages: [], next_cursor: null}
Invalid user → 404.
Cursor pagination: since filters correctly.
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_404,
    assert_422,
    create_direct_chat,
    create_user,
    send_message,
)


def test_inbox_sync_returns_messages_in_order(client):
    """Send 3 messages → inbox returns them ordered by global_seq ASC."""
    alice = create_user(client, "alice-fr2")["user_id"]
    bob = create_user(client, "bob-fr2")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    m1 = send_message(client, chat["chat_id"], alice, "First")
    m2 = send_message(client, chat["chat_id"], alice, "Second")
    m3 = send_message(client, chat["chat_id"], alice, "Third")

    r = client.get(
        "/v1/inbox",
        params={
            "user_id": bob,
            "since": 0,
            "limit": 50,
        },
    )
    body = assert_200(r)

    assert len(body["messages"]) == 3, f"Expected 3 messages, got {len(body['messages'])}"
    seqs = [msg["global_seq"] for msg in body["messages"]]
    assert seqs == sorted(seqs), "Messages not ordered by global_seq ASC"
    assert body["next_cursor"] is None  # all messages returned


def test_inbox_sync_empty(client):
    """User with no messages → empty list."""
    alice = create_user(client, "alice-fr2-empty")["user_id"]

    r = client.get(
        "/v1/inbox",
        params={
            "user_id": alice,
            "since": 0,
            "limit": 50,
        },
    )
    body = assert_200(r)

    assert body["messages"] == []
    assert body["next_cursor"] is None


def test_inbox_sync_cursor_filters(client):
    """since=<seq> returns only newer messages."""
    alice = create_user(client, "alice-fr2-cursor")["user_id"]
    bob = create_user(client, "bob-fr2-cursor")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    m1 = send_message(client, chat["chat_id"], alice, "Msg 1")
    m2 = send_message(client, chat["chat_id"], alice, "Msg 2")

    # Sync with since=m1.global_seq → should return only m2
    r = client.get(
        "/v1/inbox",
        params={
            "user_id": bob,
            "since": m1["global_seq"],
            "limit": 50,
        },
    )
    body = assert_200(r)

    assert len(body["messages"]) == 1
    assert body["messages"][0]["global_seq"] == m2["global_seq"]


def test_inbox_sync_cursor_after_all_returns_empty(client):
    """since= last seq → no new messages."""
    alice = create_user(client, "alice-fr2-all")["user_id"]
    bob = create_user(client, "bob-fr2-all")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    m1 = send_message(client, chat["chat_id"], alice, "Only")

    r = client.get(
        "/v1/inbox",
        params={
            "user_id": bob,
            "since": m1["global_seq"],
            "limit": 50,
        },
    )
    body = assert_200(r)

    assert body["messages"] == []
    assert body["next_cursor"] is None


def test_inbox_sync_unknown_user_404(client):
    """Invalid user_id → 404."""
    r = client.get(
        "/v1/inbox",
        params={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "since": 0,
            "limit": 50,
        },
    )
    assert_404(r)


def test_inbox_sync_missing_params_422(client):
    """Missing user_id or since → 422."""
    r = client.get("/v1/inbox", params={"since": 0, "limit": 50})
    assert_422(r)

    r = client.get(
        "/v1/inbox", params={"user_id": "00000000-0000-0000-0000-000000000000", "limit": 50}
    )
    assert_422(r)
