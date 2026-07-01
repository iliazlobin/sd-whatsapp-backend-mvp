"""FR-8: Get chat history.

GET /v1/chats/{chat_id}/messages?user_id=<uuid>&limit=20
→ 200 {messages: [...], next_cursor: <id>}
Cursor pagination: before=<message_id> returns older messages.
Non-member → 403. Non-existent chat → 404.
Messages ordered newest first.
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_403,
    assert_404,
    create_direct_chat,
    create_user,
    send_message,
)


def test_chat_history_returns_messages_newest_first(client):
    """Get chat history → messages ordered by created_at DESC."""
    alice = create_user(client, "alice-fr8")["user_id"]
    bob = create_user(client, "bob-fr8")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    m1 = send_message(client, chat["chat_id"], alice, "First")
    m2 = send_message(client, chat["chat_id"], alice, "Second")
    m3 = send_message(client, chat["chat_id"], alice, "Third")

    r = client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 20,
        },
    )
    body = assert_200(r)

    assert len(body["messages"]) == 3
    msg_ids = [m["message_id"] for m in body["messages"]]
    assert msg_ids[0] == m3["message_id"]  # newest first
    assert msg_ids[2] == m1["message_id"]  # oldest last
    assert "next_cursor" in body


def test_chat_history_empty(client):
    """Chat with no messages → empty list."""
    alice = create_user(client, "alice-fr8-empty")["user_id"]
    bob = create_user(client, "bob-fr8-empty")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    r = client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 20,
        },
    )
    body = assert_200(r)

    assert body["messages"] == []
    assert body["next_cursor"] is None


def test_chat_history_pagination(client):
    """Cursor pagination: before=<msg_id> returns older messages."""
    alice = create_user(client, "alice-fr8-page")["user_id"]
    bob = create_user(client, "bob-fr8-page")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    # Send 5 messages
    msgs = []
    for i in range(5):
        msgs.append(send_message(client, chat["chat_id"], alice, f"Msg {i+1}"))

    # Page 1: 3 most recent
    r1 = client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 3,
        },
    )
    body1 = assert_200(r1)
    assert len(body1["messages"]) == 3
    assert body1["next_cursor"] is not None
    cursor = body1["next_cursor"]

    # Page 2: before cursor → remaining 2
    r2 = client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 3,
            "before": cursor,
        },
    )
    body2 = assert_200(r2)
    assert len(body2["messages"]) == 2
    assert body2["next_cursor"] is None  # no more pages

    # All message_ids across pages should be unique
    page1_ids = {m["message_id"] for m in body1["messages"]}
    page2_ids = {m["message_id"] for m in body2["messages"]}
    assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"


def test_chat_history_non_member_403(client):
    """User not a member of the chat → 403."""
    alice = create_user(client, "alice-fr8-403a")["user_id"]
    bob = create_user(client, "bob-fr8-403b")["user_id"]
    charlie = create_user(client, "charlie-fr8-403")["user_id"]

    chat = create_direct_chat(client, alice, bob)

    r = client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": charlie,  # not a member
            "limit": 20,
        },
    )
    assert_403(r)


def test_chat_history_nonexistent_chat_404(client):
    """Non-existent chat → 404."""
    alice = create_user(client, "alice-fr8-404")["user_id"]

    r = client.get(
        "/v1/chats/00000000-0000-0000-0000-000000000000/messages",
        params={
            "user_id": alice,
            "limit": 20,
        },
    )
    assert_404(r)
