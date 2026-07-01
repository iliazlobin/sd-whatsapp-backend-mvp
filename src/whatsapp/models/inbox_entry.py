import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from whatsapp.models.base import Base


class InboxEntry(Base):
    __tablename__ = "inbox_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.message_id"), primary_key=True
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.chat_id"), nullable=False)
    global_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )  # "pending" | "delivered" | "read"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
