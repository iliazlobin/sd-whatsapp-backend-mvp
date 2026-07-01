import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from whatsapp.models.base import Base


class ChatMember(Base):
    __tablename__ = "chat_members"

    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.chat_id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member"
    )  # "member" | "admin"
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
