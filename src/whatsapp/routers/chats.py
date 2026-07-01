import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.database import get_session
from whatsapp.schemas.chat import (
    ChatHistoryResponse,
    ChatListResponse,
    ChatResponse,
    CreateChatRequest,
)
from whatsapp.services.chat_service import ChatService

router = APIRouter(prefix="/v1/chats", tags=["chats"])


@router.post("", status_code=http_status.HTTP_201_CREATED, response_model=ChatResponse)
async def create_chat(
    body: CreateChatRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    chat, is_duplicate = await ChatService.create_chat(
        db=db,
        chat_type=body.type,
        member_ids=body.member_ids,
        created_by=body.created_by,
        name=body.name,
    )
    member_count = await ChatService.get_member_count(db, chat.chat_id)
    await db.commit()
    response = ChatResponse(
        chat_id=chat.chat_id,
        type=chat.chat_type,
        name=chat.group_name,
        member_count=member_count,
        created_at=chat.created_at.replace(tzinfo=None),
    )
    if is_duplicate:
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
    return response


@router.get("", response_model=ChatListResponse)
async def list_chats(
    user_id: Annotated[uuid.UUID, Query(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    chats = await ChatService.list_chats(db, user_id)
    return ChatListResponse(chats=chats)


@router.get("/{chat_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Query(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    before: uuid.UUID | None = None,
):
    messages, next_cursor = await ChatService.get_chat_history(
        db=db,
        chat_id=chat_id,
        user_id=user_id,
        limit=limit,
        before=before,
    )
    return ChatHistoryResponse(
        messages=[
            {
                "message_id": msg.message_id,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "global_seq": msg.global_seq,
                "created_at": msg.created_at,
            }
            for msg in messages
        ],
        next_cursor=next_cursor,
    )
