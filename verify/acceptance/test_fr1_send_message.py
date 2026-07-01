"""FR-1: Send a text message.

POST /v1/messages {chat_id, sender_id, content, client_msg_id}
→ 201 {message_id, global_seq, status: "sent"}
Missing field → 422. Non-existent chat → 404. Non-member → 403.
"""

from verify.acceptance.conftest import (
    assert_201,
    assert_403,
    assert_404,
    assert_422,
    create_direct_chat,
    create_user,
)


def test_send_message_success(client):
    """Send a message to a chat the sender is a member of → 201."""
    alice = create_user(client, "alice-fr1")["user_id"]
    bob = create_user(client, "bob-fr1")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    r = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Hello Bob!",
            "client_msg_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    body = assert_201(r)

    assert "message_id" in body
    assert body["global_seq"] > 0
    assert body["status"] == "sent"
    assert body["duplicate"] is False


def test_send_message_missing_field_422(client):
    """Missing required field → 422."""
    alice = create_user(client, "alice-fr1-mf")["user_id"]
    bob = create_user(client, "bob-fr1-mf")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    # Missing content
    r = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "client_msg_id": "22222222-2222-2222-2222-222222222222",
        },
    )
    assert_422(r)

    # Missing chat_id
    r = client.post(
        "/v1/messages",
        json={
            "sender_id": alice,
            "content": "Hi",
            "client_msg_id": "33333333-3333-3333-3333-333333333333",
        },
    )
    assert_422(r)

    # Missing sender_id
    r = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "content": "Hi",
            "client_msg_id": "44444444-4444-4444-4444-444444444444",
        },
    )
    assert_422(r)


def test_send_message_chat_not_found_404(client):
    """Non-existent chat_id → 404."""
    alice = create_user(client, "alice-fr1-nf")["user_id"]
    fake_chat_id = "00000000-0000-0000-0000-000000000000"

    r = client.post(
        "/v1/messages",
        json={
            "chat_id": fake_chat_id,
            "sender_id": alice,
            "content": "Nobody will see this",
            "client_msg_id": "55555555-5555-5555-5555-555555555555",
        },
    )
    assert_404(r)


def test_send_message_non_member_403(client):
    """Sender is not a member of the chat → 403."""
    alice = create_user(client, "alice-fr1-nm")["user_id"]
    bob = create_user(client, "bob-fr1-nm")["user_id"]
    charlie = create_user(client, "charlie-fr1-nm")["user_id"]

    # Alice and Bob have a chat, but Charlie is not a member
    chat = create_direct_chat(client, alice, bob)

    r = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": charlie,
            "content": "I am not in this chat!",
            "client_msg_id": "66666666-6666-6666-6666-666666666666",
        },
    )
    assert_403(r)
