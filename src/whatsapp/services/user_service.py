import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models.user import User
from whatsapp.schemas.user import CreateUserRequest


class UserService:
    @staticmethod
    async def create_user(db: AsyncSession, req: CreateUserRequest) -> User:
        user = User(
            username=req.username,
            display_name=req.display_name,
        )
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail={"error": "Username already exists", "username": req.username},
            ) from None
        return user

    @staticmethod
    async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        result = await db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
        user = await UserService.get_user(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user
