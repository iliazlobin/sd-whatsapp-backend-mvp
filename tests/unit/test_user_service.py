"""Unit tests for UserService."""

import uuid

import pytest

from whatsapp.schemas.user import CreateUserRequest
from whatsapp.services.user_service import UserService


@pytest.mark.asyncio
async def test_create_user_success(db_session):
    req = CreateUserRequest(username="alice", display_name="Alice")
    user = await UserService.create_user(db_session, req)
    assert user.user_id is not None
    assert user.username == "alice"
    assert user.display_name == "Alice"


@pytest.mark.asyncio
async def test_create_user_duplicate_username(db_session):
    req = CreateUserRequest(username="bob", display_name="Bob")
    await UserService.create_user(db_session, req)

    req2 = CreateUserRequest(username="bob", display_name="Bob2")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await UserService.create_user(db_session, req2)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_user_found(db_session):
    req = CreateUserRequest(username="charlie", display_name="Charlie")
    created = await UserService.create_user(db_session, req)
    found = await UserService.get_user(db_session, created.user_id)
    assert found is not None
    assert found.username == "charlie"


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    found = await UserService.get_user(db_session, uuid.uuid4())
    assert found is None


@pytest.mark.asyncio
async def test_get_user_or_404_found(db_session):
    req = CreateUserRequest(username="dave", display_name="Dave")
    created = await UserService.create_user(db_session, req)
    found = await UserService.get_user_or_404(db_session, created.user_id)
    assert found.username == "dave"


@pytest.mark.asyncio
async def test_get_user_or_404_not_found(db_session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await UserService.get_user_or_404(db_session, uuid.uuid4())
    assert exc_info.value.status_code == 404
