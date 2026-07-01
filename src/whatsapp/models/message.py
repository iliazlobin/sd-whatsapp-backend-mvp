import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from whatsapp.models.base import Base


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.chat_id"), nullable=False, index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_msg_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, nullable=False)
    global_seq: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
