import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models.inbox_entry import InboxEntry
from whatsapp.models.message import Message
from whatsapp.services.chat_service import ChatService
from whatsapp.services.connection_manager import ConnectionManager


class MessageService:
    @staticmethod
    async def send_message(
        db: AsyncSession,
        redis,
        chat_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        client_msg_id: uuid.UUID,
        connection_manager: ConnectionManager,
    ) -> tuple[Message, bool]:
        # 1. Check Redis dedup cache
        if redis is not None:
            try:
                dedup_key = f"dedup:{client_msg_id}"
                cached = await redis.get(dedup_key)
                if cached is not None:
                    cached_id = uuid.UUID(cached)
                    existing = await db.execute(
                        select(Message).where(Message.message_id == cached_id)
                    )
                    msg = existing.scalar_one()
                    return msg, True
            except Exception:
                pass  # Redis failure should not block the send

        # 2. Validate chat exists
        await ChatService.get_chat_or_404(db, chat_id)

        # 3. Validate sender is a member
        if not await ChatService.is_member(db, chat_id, sender_id):
            raise HTTPException(
                status_code=403,
                detail={"error": "Sender is not a member of this chat"},
            )

        # 4. Check DB for existing client_msg_id (pre-insert dedup)
        existing = await db.execute(select(Message).where(Message.client_msg_id == client_msg_id))
        existing_msg = existing.scalar_one_or_none()
        if existing_msg is not None:
            # Cache in Redis for future dedup
            if redis is not None:
                try:
                    dedup_key = f"dedup:{client_msg_id}"
                    await redis.set(dedup_key, str(existing_msg.message_id), ex=86400)
                except Exception:
                    pass
            return existing_msg, True

        # 5. Get next global_seq
        seq_result = await db.execute(
            select(Message.global_seq).order_by(Message.global_seq.desc()).limit(1)
        )
        last_seq = seq_result.scalar()
        next_seq = (last_seq or 0) + 1

        # 6. Insert message
        message = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            client_msg_id=client_msg_id,
            global_seq=next_seq,
        )
        db.add(message)
        await db.flush()

        # 7. Fan-out to recipients
        recipients = await ChatService.get_recipients(db, chat_id, sender_id)
        for recipient_id in recipients:
            entry = InboxEntry(
                user_id=recipient_id,
                message_id=message.message_id,
                chat_id=chat_id,
                global_seq=message.global_seq,
                status="pending",
            )
            db.add(entry)

        # 8. Cache in Redis
        if redis is not None:
            try:
                dedup_key = f"dedup:{client_msg_id}"
                await redis.set(dedup_key, str(message.message_id), ex=86400)
            except Exception:
                pass

        # 9. Update chat last_msg_at
        chat = await ChatService.get_chat(db, chat_id)
        if chat is not None:
            chat.last_msg_at = message.created_at
            db.add(chat)

        # 10. Push to online WebSocket recipients
        push_payload = json.dumps(
            {
                "type": "new_message",
                "message": {
                    "message_id": str(message.message_id),
                    "chat_id": str(chat_id),
                    "sender_id": str(sender_id),
                    "content": content,
                    "global_seq": message.global_seq,
                    "created_at": message.created_at.isoformat(),
                },
            }
        )
        for recipient_id in recipients:
            await connection_manager.send_to_user(recipient_id, push_payload)

        return message, False

    @staticmethod
    async def get_message(db: AsyncSession, message_id: uuid.UUID) -> Message | None:
        result = await db.execute(select(Message).where(Message.message_id == message_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_message_or_404(db: AsyncSession, message_id: uuid.UUID) -> Message:
        msg = await MessageService.get_message(db, message_id)
        if msg is None:
            raise HTTPException(status_code=404, detail="Message not found")
        return msg
