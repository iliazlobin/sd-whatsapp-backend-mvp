import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateChatRequest(BaseModel):
    type: str = Field(..., pattern="^(direct|group)$")
    member_ids: list[uuid.UUID] = Field(..., min_length=1)
    created_by: uuid.UUID
    name: str | None = Field(None, max_length=256)


class ChatResponse(BaseModel):
    chat_id: uuid.UUID
    type: str
    name: str | None = None
    member_count: int
    created_at: datetime


class ChatListItem(BaseModel):
    chat_id: uuid.UUID
    type: str
    name: str | None = None
    last_msg_at: datetime | None = None
    member_count: int


class ChatListResponse(BaseModel):
    chats: list[ChatListItem]


class ChatHistoryMessageItem(BaseModel):
    message_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    global_seq: int
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessageItem]
    next_cursor: uuid.UUID | None = None
