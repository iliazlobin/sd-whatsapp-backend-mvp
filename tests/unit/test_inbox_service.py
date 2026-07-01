"""Unit tests for InboxService."""

import uuid

import pytest
from fastapi import HTTPException

from whatsapp.schemas.user import CreateUserRequest
from whatsapp.services.chat_service import ChatService
from whatsapp.services.connection_manager import ConnectionManager
from whatsapp.services.inbox_service import InboxService
from whatsapp.services.message_service import MessageService
from whatsapp.services.user_service import UserService


@pytest.fixture
async def inbox_setup(db_session):
    alice = await UserService.create_user(
        db_session, CreateUserRequest(username="alice", display_name="Alice")
    )
    bob = await UserService.create_user(
        db_session, CreateUserRequest(username="bob", display_name="Bob")
    )
    chat, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    return alice, bob, chat


@pytest.mark.asyncio
async def test_sync_inbox_returns_messages_in_order(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    import asyncio

    m1, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "First",
        uuid.uuid4(),
        cm,
    )
    await asyncio.sleep(0.01)
    m2, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Second",
        uuid.uuid4(),
        cm,
    )
    await asyncio.sleep(0.01)
    m3, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Third",
        uuid.uuid4(),
        cm,
    )

    messages, next_cursor = await InboxService.sync_inbox(
        db_session,
        bob.user_id,
        since=0,
        limit=50,
    )
    assert len(messages) == 3
    seqs = [m["global_seq"] for m in messages]
    assert seqs == sorted(seqs)
    assert next_cursor is None


@pytest.mark.asyncio
async def test_sync_inbox_empty(db_session, inbox_setup):
    alice, bob, _ = inbox_setup
    messages, next_cursor = await InboxService.sync_inbox(
        db_session,
        bob.user_id,
        since=0,
        limit=50,
    )
    assert messages == []
    assert next_cursor is None


@pytest.mark.asyncio
async def test_sync_inbox_cursor_filters(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    import asyncio

    m1, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Msg 1",
        uuid.uuid4(),
        cm,
    )
    await asyncio.sleep(0.01)
    m2, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Msg 2",
        uuid.uuid4(),
        cm,
    )

    # since=m1.global_seq should return only m2
    messages, next_cursor = await InboxService.sync_inbox(
        db_session,
        bob.user_id,
        since=m1.global_seq,
        limit=50,
    )
    assert len(messages) == 1
    assert messages[0]["global_seq"] == m2.global_seq


@pytest.mark.asyncio
async def test_sync_inbox_cursor_after_all_empty(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    m1, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Only",
        uuid.uuid4(),
        cm,
    )
    messages, next_cursor = await InboxService.sync_inbox(
        db_session,
        bob.user_id,
        since=m1.global_seq,
        limit=50,
    )
    assert messages == []
    assert next_cursor is None


@pytest.mark.asyncio
async def test_sync_inbox_unknown_user_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await InboxService.sync_inbox(
            db_session,
            uuid.uuid4(),
            since=0,
            limit=50,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_ack_delivered(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Ack me",
        uuid.uuid4(),
        cm,
    )
    msg_id, status = await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "delivered",
    )
    assert status == "delivered"

    # Verify inbox shows delivered
    messages, _ = await InboxService.sync_inbox(
        db_session,
        bob.user_id,
        since=0,
        limit=50,
    )
    assert messages[0]["status"] == "delivered"


@pytest.mark.asyncio
async def test_ack_read(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Read me",
        uuid.uuid4(),
        cm,
    )
    _, status = await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "read",
    )
    assert status == "read"


@pytest.mark.asyncio
async def test_ack_idempotent_same_status(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Idempotent",
        uuid.uuid4(),
        cm,
    )
    _, status1 = await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "delivered",
    )
    assert status1 == "delivered"

    _, status2 = await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "delivered",
    )
    assert status2 == "delivered"


@pytest.mark.asyncio
async def test_ack_monotonic_delivered_to_read(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Monotonic",
        uuid.uuid4(),
        cm,
    )
    await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "delivered",
    )
    _, status = await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "read",
    )
    assert status == "read"


@pytest.mark.asyncio
async def test_ack_no_downgrade_read_to_delivered(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "No downgrade",
        uuid.uuid4(),
        cm,
    )
    await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "read",
    )
    _, status = await InboxService.ack_message(
        db_session,
        msg.message_id,
        bob.user_id,
        "delivered",
    )
    assert status == "read"


@pytest.mark.asyncio
async def test_ack_nonexistent_message_404(db_session, inbox_setup):
    alice, _, _ = inbox_setup
    with pytest.raises(HTTPException) as exc_info:
        await InboxService.ack_message(
            db_session,
            uuid.uuid4(),
            alice.user_id,
            "delivered",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_ack_unknown_user_404(db_session, inbox_setup):
    alice, bob, chat = inbox_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Unknown user",
        uuid.uuid4(),
        cm,
    )
    # User who is not a recipient
    charlie = await UserService.create_user(
        db_session, CreateUserRequest(username="charlie", display_name="Charlie")
    )
    with pytest.raises(HTTPException) as exc_info:
        await InboxService.ack_message(
            db_session,
            msg.message_id,
            charlie.user_id,
            "delivered",
        )
    assert exc_info.value.status_code == 404
