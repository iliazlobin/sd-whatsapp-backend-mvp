"""Functional tests for inbox endpoint."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_inbox_sync_ordered(async_client):
    # Setup
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-inbox",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-inbox",
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

    # Send 3 messages
    await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "First",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Second",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Third",
            "client_msg_id": str(uuid.uuid4()),
        },
    )

    # Sync Bob's inbox
    r = await async_client.get(
        "/v1/inbox",
        params={
            "user_id": bob,
            "since": 0,
            "limit": 50,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["messages"]) == 3
    seqs = [m["global_seq"] for m in body["messages"]]
    assert seqs == sorted(seqs)
    assert body["next_cursor"] is None


@pytest.mark.asyncio
async def test_inbox_sync_empty(async_client):
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "empty-ft",
            "display_name": "Empty",
        },
    )
    user_id = r.json()["user_id"]

    r = await async_client.get(
        "/v1/inbox",
        params={
            "user_id": user_id,
            "since": 0,
            "limit": 50,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["messages"] == []
    assert body["next_cursor"] is None


@pytest.mark.asyncio
async def test_inbox_sync_cursor(async_client):
    # Setup
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "alice-ft-cursor",
            "display_name": "Alice",
        },
    )
    alice = r.json()["user_id"]
    r = await async_client.post(
        "/v1/users",
        json={
            "username": "bob-ft-cursor",
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

    r1 = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Msg 1",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    _r2 = await async_client.post(
        "/v1/messages",
        json={
            "chat_id": chat["chat_id"],
            "sender_id": alice,
            "content": "Msg 2",
            "client_msg_id": str(uuid.uuid4()),
        },
    )
    m1 = r1.json()

    # since=m1.global_seq should return only m2
    r = await async_client.get(
        "/v1/inbox",
        params={
            "user_id": bob,
            "since": m1["global_seq"],
            "limit": 50,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["messages"]) == 1


@pytest.mark.asyncio
async def test_inbox_sync_unknown_user_404(async_client):
    r = await async_client.get(
        "/v1/inbox",
        params={
            "user_id": str(uuid.uuid4()),
            "since": 0,
            "limit": 50,
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_inbox_sync_missing_params_422(async_client):
    r = await async_client.get("/v1/inbox", params={"since": 0, "limit": 50})
    assert r.status_code == 422

    r = await async_client.get(
        "/v1/inbox",
        params={
            "user_id": str(uuid.uuid4()),
            "limit": 50,
        },
    )
    assert r.status_code == 422
