import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models.chat import Chat
from whatsapp.models.chat_member import ChatMember
from whatsapp.models.message import Message
from whatsapp.models.user import User
from whatsapp.services.user_service import UserService


class ChatService:
    @staticmethod
    async def create_chat(
        db: AsyncSession,
        chat_type: str,
        member_ids: list[uuid.UUID],
        created_by: uuid.UUID,
        name: str | None = None,
    ) -> tuple[Chat, bool]:
        # Validate member count
        if chat_type == "direct":
            if len(member_ids) != 2:
                raise HTTPException(
                    status_code=422, detail="Direct chat requires exactly 2 members"
                )
        elif chat_type == "group":
            if len(member_ids) < 2:
                raise HTTPException(
                    status_code=422, detail="Group chat requires at least 2 members"
                )
            if len(member_ids) > 256:
                raise HTTPException(status_code=422, detail="Group chat cannot exceed 256 members")
            if not name:
                raise HTTPException(status_code=422, detail="Group chat name is required")

        # created_by must be in member_ids
        if created_by not in member_ids:
            raise HTTPException(status_code=422, detail="created_by must be in member_ids")

        # Validate all users exist
        deduped = list(dict.fromkeys(member_ids))
        users_result = await db.execute(select(User.user_id).where(User.user_id.in_(deduped)))
        # Normalize to str on both sides: SQLite returns user_id as a string while the
        # request-parsed ids are uuid.UUID — a raw set-membership check would then miss
        # a just-created user and wrongly 404 (dialect-robust across SQLite + Postgres).
        found_ids = {str(row[0]) for row in users_result.fetchall()}
        for uid in deduped:
            if str(uid) not in found_ids:
                raise HTTPException(status_code=404, detail=f"User not found: {uid}")

        if chat_type == "direct":
            # Find existing direct chat with both members
            subq = (
                select(ChatMember.chat_id)
                .where(ChatMember.user_id.in_(member_ids))
                .group_by(ChatMember.chat_id)
                .having(func.count(ChatMember.user_id) == 2)
                .subquery()
            )
            result = await db.execute(
                select(Chat).where(
                    Chat.chat_id.in_(select(subq.c.chat_id)),
                    Chat.chat_type == "direct",
                )
            )
            existing_chat = result.scalars().first()
            if existing_chat is not None:
                return existing_chat, True

            # Create new direct chat
            chat = Chat(
                chat_type="direct",
                group_name=None,
                created_by=created_by,
            )
            db.add(chat)
            await db.flush()

            for uid in member_ids:
                db.add(
                    ChatMember(
                        chat_id=chat.chat_id,
                        user_id=uid,
                        role="member",
                    )
                )
            await db.flush()
            return chat, False

        else:  # group
            chat = Chat(
                chat_type="group",
                group_name=name,
                created_by=created_by,
            )
            db.add(chat)
            await db.flush()

            for uid in deduped:
                role = "admin" if uid == created_by else "member"
                db.add(
                    ChatMember(
                        chat_id=chat.chat_id,
                        user_id=uid,
                        role=role,
                    )
                )
            await db.flush()
            return chat, False

    @staticmethod
    async def get_chat(db: AsyncSession, chat_id: uuid.UUID) -> Chat | None:
        result = await db.execute(select(Chat).where(Chat.chat_id == chat_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_chat_or_404(db: AsyncSession, chat_id: uuid.UUID) -> Chat:
        chat = await ChatService.get_chat(db, chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chat

    @staticmethod
    async def get_member_count(db: AsyncSession, chat_id: uuid.UUID) -> int:
        result = await db.execute(select(func.count()).where(ChatMember.chat_id == chat_id))
        return result.scalar() or 0

    @staticmethod
    async def is_member(db: AsyncSession, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_recipients(
        db: AsyncSession, chat_id: uuid.UUID, exclude_user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await db.execute(
            select(ChatMember.user_id).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id != exclude_user_id,
            )
        )
        return [row[0] for row in result.fetchall()]

    @staticmethod
    async def list_chats(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
        await UserService.get_user_or_404(db, user_id)

        # Query chats the user is a member of, with member count
        result = await db.execute(
            select(
                Chat.chat_id,
                Chat.chat_type,
                Chat.group_name,
                Chat.last_msg_at,
                func.count(ChatMember.user_id).label("member_count"),
            )
            .join(ChatMember, Chat.chat_id == ChatMember.chat_id)
            .where(
                Chat.chat_id.in_(select(ChatMember.chat_id).where(ChatMember.user_id == user_id))
            )
            .group_by(Chat.chat_id)
            .order_by(Chat.last_msg_at.desc().nullslast())
        )
        rows = result.fetchall()
        return [
            {
                "chat_id": row.chat_id,
                "type": row.chat_type,
                "name": row.group_name,
                "last_msg_at": row.last_msg_at,
                "member_count": row.member_count,
            }
            for row in rows
        ]

    @staticmethod
    async def get_chat_history(
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 20,
        before: uuid.UUID | None = None,
    ) -> tuple[list[Message], uuid.UUID | None]:
        # Validate chat exists and user is member
        await ChatService.get_chat_or_404(db, chat_id)
        if not await ChatService.is_member(db, chat_id, user_id):
            raise HTTPException(status_code=403, detail="User is not a member of this chat")

        query = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.global_seq.desc())
            .limit(limit + 1)
        )
        if before is not None:
            # Get the global_seq of the cursor message for pagination
            cursor_msg = await db.execute(
                select(Message.global_seq).where(Message.message_id == before)
            )
            cursor_seq = cursor_msg.scalar_one_or_none()
            if cursor_seq is not None:
                query = query.where(Message.global_seq < cursor_seq)

        result = await db.execute(query)
        messages = result.scalars().all()

        next_cursor = None
        if len(messages) > limit:
            messages = messages[:limit]
            next_cursor = messages[-1].message_id

        return messages, next_cursor
