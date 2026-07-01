"""Unit tests for MessageService."""

import uuid

import pytest
from fastapi import HTTPException

from whatsapp.schemas.user import CreateUserRequest
from whatsapp.services.chat_service import ChatService
from whatsapp.services.connection_manager import ConnectionManager
from whatsapp.services.message_service import MessageService
from whatsapp.services.user_service import UserService


@pytest.fixture
async def chat_setup(db_session):
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
async def test_send_message_success(db_session, chat_setup):
    alice, bob, chat = chat_setup
    cm = ConnectionManager()
    msg, is_dup = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Hello!",
        uuid.uuid4(),
        cm,
    )
    assert not is_dup
    assert msg.content == "Hello!"
    assert msg.global_seq >= 1
    assert msg.chat_id == chat.chat_id
    assert msg.sender_id == alice.user_id


@pytest.mark.asyncio
async def test_send_message_creates_inbox_entries(db_session, chat_setup):
    alice, bob, chat = chat_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Hello Bob!",
        uuid.uuid4(),
        cm,
    )
    from sqlalchemy import select

    from whatsapp.models.inbox_entry import InboxEntry

    result = await db_session.execute(
        select(InboxEntry).where(InboxEntry.message_id == msg.message_id)
    )
    entries = result.scalars().all()
    # Bob should have an inbox entry, Alice (sender) should not
    recipient_ids = {e.user_id for e in entries}
    assert bob.user_id in recipient_ids
    assert alice.user_id not in recipient_ids


@pytest.mark.asyncio
async def test_send_message_dedup_same_client_msg_id(db_session, chat_setup):
    alice, bob, chat = chat_setup
    cm = ConnectionManager()
    client_msg_id = uuid.uuid4()

    msg1, is_dup1 = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Original",
        client_msg_id,
        cm,
    )
    assert not is_dup1

    msg2, is_dup2 = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Duplicate",
        client_msg_id,
        cm,
    )
    assert is_dup2
    assert msg2.message_id == msg1.message_id
    assert msg2.global_seq == msg1.global_seq


@pytest.mark.asyncio
async def test_send_message_different_client_msg_id(db_session, chat_setup):
    alice, bob, chat = chat_setup
    cm = ConnectionManager()
    msg1, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Msg A",
        uuid.uuid4(),
        cm,
    )
    msg2, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Msg B",
        uuid.uuid4(),
        cm,
    )
    assert msg1.message_id != msg2.message_id
    assert msg1.global_seq != msg2.global_seq


@pytest.mark.asyncio
async def test_send_message_non_member_403(db_session, chat_setup):
    alice, bob, chat = chat_setup
    charlie = await UserService.create_user(
        db_session, CreateUserRequest(username="charlie", display_name="Charlie")
    )
    cm = ConnectionManager()
    with pytest.raises(HTTPException) as exc_info:
        await MessageService.send_message(
            db_session,
            None,
            chat.chat_id,
            charlie.user_id,
            "Intruder!",
            uuid.uuid4(),
            cm,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_send_message_nonexistent_chat_404(db_session, chat_setup):
    alice, _, _ = chat_setup
    cm = ConnectionManager()
    with pytest.raises(HTTPException) as exc_info:
        await MessageService.send_message(
            db_session,
            None,
            uuid.uuid4(),
            alice.user_id,
            "Hello?",
            uuid.uuid4(),
            cm,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_message_found(db_session, chat_setup):
    alice, bob, chat = chat_setup
    cm = ConnectionManager()
    msg, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Test",
        uuid.uuid4(),
        cm,
    )
    found = await MessageService.get_message(db_session, msg.message_id)
    assert found is not None
    assert found.message_id == msg.message_id


@pytest.mark.asyncio
async def test_get_message_not_found(db_session):
    found = await MessageService.get_message(db_session, uuid.uuid4())
    assert found is None
