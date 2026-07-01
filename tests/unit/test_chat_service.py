"""Unit tests for ChatService."""

import uuid

import pytest
from fastapi import HTTPException

from whatsapp.schemas.user import CreateUserRequest
from whatsapp.services.chat_service import ChatService
from whatsapp.services.user_service import UserService


@pytest.fixture
async def three_users(db_session):
    u1 = await UserService.create_user(
        db_session, CreateUserRequest(username="alice", display_name="Alice")
    )
    u2 = await UserService.create_user(
        db_session, CreateUserRequest(username="bob", display_name="Bob")
    )
    u3 = await UserService.create_user(
        db_session, CreateUserRequest(username="charlie", display_name="Charlie")
    )
    return u1, u2, u3


@pytest.mark.asyncio
async def test_create_direct_chat_success(db_session, three_users):
    alice, bob, _ = three_users
    chat, is_dup = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    assert not is_dup
    assert chat.chat_type == "direct"
    assert chat.group_name is None


@pytest.mark.asyncio
async def test_create_direct_chat_idempotent(db_session, three_users):
    alice, bob, _ = three_users
    chat1, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    chat2, is_dup = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    assert is_dup
    assert chat2.chat_id == chat1.chat_id


@pytest.mark.asyncio
async def test_create_direct_chat_reversed_order_idempotent(db_session, three_users):
    alice, bob, _ = three_users
    chat1, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    chat2, is_dup = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[bob.user_id, alice.user_id],
        created_by=bob.user_id,
    )
    assert is_dup
    assert chat2.chat_id == chat1.chat_id


@pytest.mark.asyncio
async def test_create_direct_chat_single_member_422(db_session, three_users):
    alice, _, _ = three_users
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.create_chat(
            db_session,
            chat_type="direct",
            member_ids=[alice.user_id],
            created_by=alice.user_id,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_direct_chat_three_members_422(db_session, three_users):
    alice, bob, charlie = three_users
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.create_chat(
            db_session,
            chat_type="direct",
            member_ids=[alice.user_id, bob.user_id, charlie.user_id],
            created_by=alice.user_id,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_direct_chat_creator_not_member_422(db_session, three_users):
    alice, bob, charlie = three_users
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.create_chat(
            db_session,
            chat_type="direct",
            member_ids=[alice.user_id, bob.user_id],
            created_by=charlie.user_id,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_group_chat_success(db_session, three_users):
    alice, bob, charlie = three_users
    chat, is_dup = await ChatService.create_chat(
        db_session,
        chat_type="group",
        member_ids=[alice.user_id, bob.user_id, charlie.user_id],
        created_by=alice.user_id,
        name="Study Group",
    )
    assert not is_dup
    assert chat.chat_type == "group"
    assert chat.group_name == "Study Group"


@pytest.mark.asyncio
async def test_create_group_chat_creator_is_admin(db_session, three_users):
    alice, bob, _ = three_users
    chat, _ = await ChatService.create_chat(
        db_session,
        chat_type="group",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
        name="Test Group",
    )
    from sqlalchemy import select

    from whatsapp.models.chat_member import ChatMember

    result = await db_session.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat.chat_id,
            ChatMember.user_id == alice.user_id,
        )
    )
    member = result.scalar_one()
    assert member.role == "admin"


@pytest.mark.asyncio
async def test_create_group_chat_empty_name_422(db_session, three_users):
    alice, bob, _ = three_users
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.create_chat(
            db_session,
            chat_type="group",
            member_ids=[alice.user_id, bob.user_id],
            created_by=alice.user_id,
            name="",
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_group_chat_too_many_members_422(db_session):
    alice = await UserService.create_user(
        db_session, CreateUserRequest(username="alice", display_name="Alice")
    )
    # Generate 257 member IDs
    member_ids = [alice.user_id] + [uuid.uuid4() for _ in range(256)]
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.create_chat(
            db_session,
            chat_type="group",
            member_ids=member_ids,
            created_by=alice.user_id,
            name="Huge Group",
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_list_chats(db_session, three_users):
    alice, bob, charlie = three_users
    await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    await ChatService.create_chat(
        db_session,
        chat_type="group",
        member_ids=[alice.user_id, charlie.user_id],
        created_by=alice.user_id,
        name="Group 1",
    )
    chats = await ChatService.list_chats(db_session, alice.user_id)
    assert len(chats) == 2


@pytest.mark.asyncio
async def test_is_member(db_session, three_users):
    alice, bob, _ = three_users
    chat, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    assert await ChatService.is_member(db_session, chat.chat_id, alice.user_id)
    assert await ChatService.is_member(db_session, chat.chat_id, bob.user_id)
    stranger = uuid.uuid4()
    assert not await ChatService.is_member(db_session, chat.chat_id, stranger)


@pytest.mark.asyncio
async def test_get_chat_history_newest_first(db_session, three_users):
    alice, bob, _ = three_users
    chat, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    from whatsapp.services.connection_manager import ConnectionManager
    from whatsapp.services.message_service import MessageService

    cm = ConnectionManager()
    msg1, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "First",
        uuid.uuid4(),
        cm,
    )
    import asyncio

    await asyncio.sleep(0.01)
    msg2, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Second",
        uuid.uuid4(),
        cm,
    )
    await asyncio.sleep(0.01)
    msg3, _ = await MessageService.send_message(
        db_session,
        None,
        chat.chat_id,
        alice.user_id,
        "Third",
        uuid.uuid4(),
        cm,
    )

    messages, next_cursor = await ChatService.get_chat_history(
        db_session,
        chat.chat_id,
        alice.user_id,
        limit=20,
    )
    assert len(messages) == 3
    # Newest first
    assert messages[0].message_id == msg3.message_id
    assert messages[2].message_id == msg1.message_id
    assert next_cursor is None


@pytest.mark.asyncio
async def test_get_chat_history_pagination(db_session, three_users):
    alice, bob, _ = three_users
    chat, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    from whatsapp.services.connection_manager import ConnectionManager
    from whatsapp.services.message_service import MessageService

    cm = ConnectionManager()
    import asyncio

    for i in range(5):
        await MessageService.send_message(
            db_session,
            None,
            chat.chat_id,
            alice.user_id,
            f"Msg {i+1}",
            uuid.uuid4(),
            cm,
        )
        await asyncio.sleep(0.01)

    # Page 1: 3 newest
    page1, cursor = await ChatService.get_chat_history(
        db_session,
        chat.chat_id,
        alice.user_id,
        limit=3,
    )
    assert len(page1) == 3
    assert cursor is not None

    # Page 2: before cursor
    page2, cursor2 = await ChatService.get_chat_history(
        db_session,
        chat.chat_id,
        alice.user_id,
        limit=3,
        before=cursor,
    )
    assert len(page2) == 2
    assert cursor2 is None


@pytest.mark.asyncio
async def test_get_chat_history_non_member_403(db_session, three_users):
    alice, bob, charlie = three_users
    chat, _ = await ChatService.create_chat(
        db_session,
        chat_type="direct",
        member_ids=[alice.user_id, bob.user_id],
        created_by=alice.user_id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.get_chat_history(
            db_session,
            chat.chat_id,
            charlie.user_id,
            limit=20,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_chat_history_nonexistent_chat_404(db_session, three_users):
    alice, _, _ = three_users
    with pytest.raises(HTTPException) as exc_info:
        await ChatService.get_chat_history(
            db_session,
            uuid.uuid4(),
            alice.user_id,
            limit=20,
        )
    assert exc_info.value.status_code == 404
