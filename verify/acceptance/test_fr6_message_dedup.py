"""FR-6: Message deduplication.

POST /v1/messages with duplicate client_msg_id within 24h
→ 200 {message_id, global_seq, status, duplicate: true}
After 24h TTL → 201 (new message).
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_201,
    create_direct_chat,
    create_user,
)


def test_duplicate_client_msg_id_returns_original(client):
    """Sending with same client_msg_id twice → 200 with duplicate:true."""
    alice = create_user(client, "alice-fr6")["user_id"]
    bob = create_user(client, "bob-fr6")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    client_msg_id = "dedup-1111-1111-1111-111111111111"

    # First send → 201
    r1 = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Original message",
            "client_msg_id": client_msg_id,
        },
    )
    body1 = assert_201(r1)
    assert body1["duplicate"] is False

    # Second send with same client_msg_id → 200 duplicate
    r2 = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "This should be ignored",
            "client_msg_id": client_msg_id,
        },
    )
    body2 = assert_200(r2)

    assert (
        body2["message_id"] == body1["message_id"]
    ), f"Duplicate should return original message_id. Got {body2['message_id']}, expected {body1['message_id']}"
    assert body2["global_seq"] == body1["global_seq"], "Duplicate should return original global_seq"
    assert body2["duplicate"] is True


def test_duplicate_with_different_content_returns_original(client):
    """Even with different content, same client_msg_id returns original."""
    alice = create_user(client, "alice-fr6-diff")["user_id"]
    bob = create_user(client, "bob-fr6-diff")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    client_msg_id = "dedup-2222-2222-2222-222222222222"

    r1 = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "First content",
            "client_msg_id": client_msg_id,
        },
    )
    body1 = assert_201(r1)

    r2 = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Completely different content, should be ignored",
            "client_msg_id": client_msg_id,
        },
    )
    body2 = assert_200(r2)

    assert body2["message_id"] == body1["message_id"]
    assert body2["duplicate"] is True


def test_different_client_msg_ids_create_new_messages(client):
    """Different client_msg_id → different message created."""
    alice = create_user(client, "alice-fr6-diff2")["user_id"]
    bob = create_user(client, "bob-fr6-diff2")["user_id"]
    chat = create_direct_chat(client, alice, bob)

    r1 = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Message A",
            "client_msg_id": "dedup-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    )
    body1 = assert_201(r1)

    r2 = client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Message B",
            "client_msg_id": "dedup-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        },
    )
    body2 = assert_201(r2)

    assert body1["message_id"] != body2["message_id"]
    assert body1["global_seq"] != body2["global_seq"]
