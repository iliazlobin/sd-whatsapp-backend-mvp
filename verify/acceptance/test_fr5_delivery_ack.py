"""FR-5: Delivery acknowledgement (ACK).

POST /v1/messages/{message_id}/ack {user_id, status: "delivered"|"read"}
→ 200 {message_id, status}
Already acknowledged → 200 (idempotent).
Non-existent message → 404. Unknown user → 404.
Monotonic: pending → delivered → read. Never regresses.
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_404,
    create_direct_chat,
    create_user,
    get_inbox,
    send_message,
)


def test_ack_delivered(client):
    """Ack as delivered → status updated."""
    alice = create_user(client, "alice-fr5")["user_id"]
    bob = create_user(client, "bob-fr5")["user_id"]
    chat = create_direct_chat(client, alice, bob)
    msg = send_message(client, chat["chat_id"], alice, "Ack me")

    r = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "delivered",
        },
    )
    body = assert_200(r)

    assert body["message_id"] == msg["message_id"]
    assert body["status"] == "delivered"

    # Verify inbox now shows delivered
    inbox = get_inbox(client, bob, since=0)
    assert inbox["messages"][0]["status"] == "delivered"


def test_ack_read(client):
    """Ack as read → status updated to read."""
    alice = create_user(client, "alice-fr5-read")["user_id"]
    bob = create_user(client, "bob-fr5-read")["user_id"]
    chat = create_direct_chat(client, alice, bob)
    msg = send_message(client, chat["chat_id"], alice, "Read me")

    r = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "read",
        },
    )
    body = assert_200(r)
    assert body["status"] == "read"


def test_ack_idempotent_same_status(client):
    """Re-ACK with same status → 200 idempotent."""
    alice = create_user(client, "alice-fr5-idem")["user_id"]
    bob = create_user(client, "bob-fr5-idem")["user_id"]
    chat = create_direct_chat(client, alice, bob)
    msg = send_message(client, chat["chat_id"], alice, "Idempotent ACK")

    # First ack
    r1 = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "delivered",
        },
    )
    body1 = assert_200(r1)
    assert body1["status"] == "delivered"

    # Second ack same status
    r2 = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "delivered",
        },
    )
    body2 = assert_200(r2)
    assert body2["status"] == "delivered"


def test_ack_monotonic_delivered_to_read(client):
    """Ack delivered then read → status upgrades."""
    alice = create_user(client, "alice-fr5-mono")["user_id"]
    bob = create_user(client, "bob-fr5-mono")["user_id"]
    chat = create_direct_chat(client, alice, bob)
    msg = send_message(client, chat["chat_id"], alice, "Monotonic")

    # Delivered
    client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "delivered",
        },
    )

    # Then read
    r2 = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "read",
        },
    )
    body2 = assert_200(r2)
    assert body2["status"] == "read"


def test_ack_no_downgrade_read_to_delivered(client):
    """Ack read then try delivered → stays read (monotonic, no downgrade)."""
    alice = create_user(client, "alice-fr5-nodn")["user_id"]
    bob = create_user(client, "bob-fr5-nodn")["user_id"]
    chat = create_direct_chat(client, alice, bob)
    msg = send_message(client, chat["chat_id"], alice, "No downgrade")

    # Ack as read first
    client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "read",
        },
    )

    # Try to downgrade to delivered
    r2 = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "delivered",
        },
    )
    body2 = assert_200(r2)
    assert body2["status"] == "read"  # stays read


def test_ack_nonexistent_message_404(client):
    """ACK on non-existent message → 404."""
    alice = create_user(client, "alice-fr5-404")["user_id"]

    r = client.post(
        "/v1/messages/00000000-0000-0000-0000-000000000000/ack",
        json={
            "user_id": alice,
            "status": "delivered",
        },
    )
    assert_404(r)


def test_ack_unknown_user_404(client):
    """ACK from unknown user → 404."""
    alice = create_user(client, "alice-fr5-uu")["user_id"]
    bob = create_user(client, "bob-fr5-uu")["user_id"]
    chat = create_direct_chat(client, alice, bob)
    msg = send_message(client, chat["chat_id"], alice, "Unknown user ACK")

    r = client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "status": "delivered",
        },
    )
    assert_404(r)
