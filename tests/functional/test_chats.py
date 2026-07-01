"""Functional tests for chats endpoint."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_direct_chat(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-dc",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-dc",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]

    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "chat_id" in body
    assert body["type"] == "direct"
    assert body["name"] is None
    assert body["member_count"] == 2
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_direct_chat_idempotent(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-idem",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-idem",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]

    r1 = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert r1.status_code == 201
    chat1 = r1.json()

    r2 = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert r2.status_code == 200
    chat2 = r2.json()
    assert chat2["chat_id"] == chat1["chat_id"]


@pytest.mark.asyncio
async def test_create_direct_chat_reversed_order(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-rev",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-rev",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]

    r1 = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert r1.status_code == 201
    chat1 = r1.json()

    r2 = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [bob, alice],
            "created_by": bob,
        },
    )
    assert r2.status_code == 200
    chat2 = r2.json()
    assert chat2["chat_id"] == chat1["chat_id"]


@pytest.mark.asyncio
async def test_create_group_chat(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-gc",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-gc",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "charlie-ft-gc",
            "display_name": "Charlie",
        },
    )
    charlie = r.json()["user_id"]

    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "Study Group",
            "member_ids": [alice, bob, charlie],
            "created_by": alice,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "group"
    assert body["name"] == "Study Group"
    assert body["member_count"] == 3


@pytest.mark.asyncio
async def test_create_group_chat_empty_name_422(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-en",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-en",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]

    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "group",
            "name": "",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_history(async_client):
    # Setup
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-hist",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-hist",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]
    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    chat = r.json()

    # Send messages
    r1 = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "First",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    r2 = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Second",
            "client_msg_id": str(uuid.uuid4()),
        },
    )

    # Get history
    r = await async_client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 20,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["messages"]) == 2
    # Newest first
    assert body["messages"][0]["message_id"] == r2.json()["message_id"]
    assert body["messages"][1]["message_id"] == r1.json()["message_id"]


@pytest.mark.asyncio
async def test_chat_history_pagination(async_client):
    # Setup
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-page",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-page",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]
    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    chat = r.json()

    # Send 5 messages
    for i in range(5):
        await async_client.post(
            "/v1/messages",
            json={
                "chat_id": chat["chat_id"],
                "sender_id": alice,
                "content": f"Msg {i+1}",
                "client_msg_id": str(uuid.uuid4()),
            },
        )

    # Page 1: 3 newest
    r = await async_client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 3,
        },
    )
    assert r.status_code == 200
    page1 = r.json()
    assert len(page1["messages"]) == 3
    assert page1["next_cursor"] is not None

    # Page 2: before cursor
    r = await async_client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": alice,
            "limit": 3,
            "before": page1["next_cursor"],
        },
    )
    assert r.status_code == 200
    page2 = r.json()
    assert len(page2["messages"]) == 2
    assert page2["next_cursor"] is None


@pytest.mark.asyncio
async def test_chat_history_non_member_403(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-403",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-403",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "charlie-ft-403",
            "display_name": "Charlie",
        },
    )
    charlie = r.json()["user_id"]

    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    chat = r.json()

    r = await async_client.get(
        f"/v1/chats/{chat['chat_id']}/messages",
        params={
            "user_id": charlie,
            "limit": 20,
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_chat_history_nonexistent_chat_404(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-404",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]

    r = await async_client.get(
        f"/v1/chats/{str(uuid.uuid4())}/messages",
        params={
            "user_id": alice,
            "limit": 20,
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delivery_ack(async_client):
    # Setup
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-ack",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-ack",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]
    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    chat = r.json()

    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Ack me",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    msg = r.json()

    # ACK
    r = await async_client.post(
        f"/v1/messages/{msg['message_id']}/ack",
        json={
            "user_id": bob,
            "status": "delivered",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["message_id"] == msg["message_id"]
    assert body["status"] == "delivered"

    # Verify inbox reflects ack
    r = await async_client.get(
        "/v1/inbox",
        params={
            "user_id": bob,
            "since": 0,
            "limit": 50,
        },
    )
    inbox = r.json()
    assert inbox["messages"][0]["status"] == "delivered"
