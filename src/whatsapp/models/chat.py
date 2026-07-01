import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from whatsapp.models.base import Base


class Chat(Base):
    __tablename__ = "chats"

    chat_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chat_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "direct" | "group"
    group_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_msg_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
