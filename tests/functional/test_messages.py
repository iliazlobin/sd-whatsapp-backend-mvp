"""Functional tests for messages endpoint."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_send_message_success(async_client):
    # Create users
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-msg",
            "display_name": "Alice",
        },
    )
    assert r.status_code == 201
    alice = r.json()["user_id"]

    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-msg",
            "display_name": "Bob",
        },
    )
    assert r.status_code == 201
    bob = r.json()["user_id"]

    # Create chat
    r = await async_client.post(
        "/v1/chats",
        json={
            "type": "direct",
            "member_ids": [alice, bob],
            "created_by": alice,
        },
    )
    assert r.status_code in (200, 201)
    chat = r.json()

    # Send message
    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Hello Bob!",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "message_id" in body
    assert body["global_seq"] > 0
    assert body["status"] == "sent"
    assert body["duplicate"] is False


@pytest.mark.asyncio
async def test_send_message_missing_field_422(async_client):
    # Create users
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-mf",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-mf",
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

    # Missing content
    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 422

    # Missing chat_id
    r = await async_client.post(
        "/v1/messages",
        json={
            "sender_id": alice,
            "content": "Hi",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 422

    # Missing sender_id
    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "content": "Hi",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_send_message_chat_not_found_404(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-nf",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]

    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": str(uuid.uuid4()),
            "sender_id": alice,
            "content": "Hello?",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_send_message_non_member_403(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-nm",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-nm",
            "display_name": "Bob",
        },
    )
    bob = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "charlie-ft-nm",
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

    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": charlie,
            "content": "Intruder!",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_message_dedup(async_client):
    # Setup
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-dedup",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-dedup",
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

    client_msg_id = str(uuid.uuid4())

    # First send → 201
    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Original",
            "client_msg_id": client_msg_id,
        },
    )
    assert r.status_code == 201
    body1 = r.json()
    assert body1["duplicate"] is False

    # Second send same client_msg_id → 200
    r = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Duplicate",
            "client_msg_id": client_msg_id,
        },
    )
    assert r.status_code == 200
    body2 = r.json()
    assert body2["duplicate"] is True
    assert body2["message_id"] == body1["message_id"]
