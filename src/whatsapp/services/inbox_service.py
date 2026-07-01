import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models.inbox_entry import InboxEntry
from whatsapp.models.message import Message
from whatsapp.services.message_service import MessageService
from whatsapp.services.user_service import UserService

STATUS_ORDER = {"pending": 0, "delivered": 1, "read": 2}


class InboxService:
    @staticmethod
    async def sync_inbox(
        db: AsyncSession,
        user_id: uuid.UUID,
        since: int,
        limit: int = 50,
    ) -> tuple[list[dict], int | None]:
        # Validate user exists
        await UserService.get_user_or_404(db, user_id)

        # Range scan: inbox_entries WHERE user_id = X AND global_seq > Y ORDER BY global_seq
        query = (
            select(InboxEntry, Message.content, Message.sender_id)
            .join(Message, InboxEntry.message_id == Message.message_id)
            .where(
                InboxEntry.user_id == user_id,
                InboxEntry.global_seq > since,
            )
            .order_by(InboxEntry.global_seq.asc())
            .limit(limit + 1)
        )
        result = await db.execute(query)
        rows = result.fetchall()

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        messages = []
        for inbox_entry, content, sender_id in rows:
            messages.append(
                {
                    "message_id": str(inbox_entry.message_id),
                    "chat_id": str(inbox_entry.chat_id),
                    "sender_id": str(sender_id),
                    "content": content,
                    "global_seq": inbox_entry.global_seq,
                    "status": inbox_entry.status,
                    "created_at": inbox_entry.created_at.isoformat(),
                }
            )

        next_cursor = rows[-1].InboxEntry.global_seq if (has_more and rows) else None
        return messages, next_cursor

    @staticmethod
    async def ack_message(
        db: AsyncSession,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        status: str,
    ) -> tuple[str, str]:
        # Validate message exists
        await MessageService.get_message_or_404(db, message_id)

        # Validate user exists
        await UserService.get_user_or_404(db, user_id)

        # Find the inbox entry
        result = await db.execute(
            select(InboxEntry).where(
                InboxEntry.user_id == user_id,
                InboxEntry.message_id == message_id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=404, detail="Inbox entry not found")

        # Monotonic status check
        current_order = STATUS_ORDER.get(entry.status, 0)
        new_order = STATUS_ORDER.get(status, 0)

        if new_order <= current_order:
            # Idempotent or downgrade attempt — return current status
            effective_status = entry.status
        else:
            # Upgrade status
            entry.status = status
            effective_status = status

        await db.flush()
        return str(message_id), effective_status
