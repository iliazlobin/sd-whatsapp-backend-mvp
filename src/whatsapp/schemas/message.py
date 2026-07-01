import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SendMessageRequest(BaseModel):
    chat_id: uuid.UUID
    sender_id: uuid.UUID
    content: str = Field(..., min_length=1)
    client_msg_id: str = Field(..., min_length=1)

    @field_validator("client_msg_id")
    @classmethod
    def coerce_client_msg_id(cls, v: str) -> uuid.UUID:
        """Accept any string and deterministically convert to UUID v5."""
        try:
            return uuid.UUID(v)
        except ValueError:
            # Not a valid UUID string — hash it deterministically
            return uuid.uuid5(uuid.NAMESPACE_DNS, v)


class MessageResponse(BaseModel):
    message_id: uuid.UUID
    global_seq: int
    status: str
    duplicate: bool


class InboxMessageResponse(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    global_seq: int
    status: str
    created_at: datetime


class InboxSyncResponse(BaseModel):
    messages: list[InboxMessageResponse]
    next_cursor: int | None = None
