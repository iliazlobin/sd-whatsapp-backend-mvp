import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.database import get_session
from whatsapp.schemas.user import CreateUserRequest, UserResponse
from whatsapp.services.user_service import UserService

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", status_code=http_status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await UserService.create_user(db, body)
    await db.commit()
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await UserService.get_user_or_404(db, user_id)
    return user
