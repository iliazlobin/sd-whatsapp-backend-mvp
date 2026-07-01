import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.database import get_session
from whatsapp.redis import get_redis
from whatsapp.schemas.ack import AckRequest
from whatsapp.schemas.message import MessageResponse, SendMessageRequest
from whatsapp.services.connection_manager import connection_manager
from whatsapp.services.inbox_service import InboxService
from whatsapp.services.message_service import MessageService

router = APIRouter(prefix="/v1/messages", tags=["messages"])


@router.post("", response_model=MessageResponse)
async def send_message(
    body: SendMessageRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[None, Depends(get_redis)] = None,
):
    message, is_duplicate = await MessageService.send_message(
        db=db,
        redis=redis,
        chat_id=body.chat_id,
        sender_id=body.sender_id,
        content=body.content,
        client_msg_id=body.client_msg_id,
        connection_manager=connection_manager,
    )
    await db.commit()
    response = MessageResponse(
        message_id=message.message_id,
        global_seq=message.global_seq,
        status="sent",
        duplicate=is_duplicate,
    )
    status = 200 if is_duplicate else 201
    return JSONResponse(status_code=status, content=response.model_dump(mode="json"))


@router.post("/{message_id}/ack")
async def ack_message(
    message_id: uuid.UUID,
    body: AckRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    msg_id, status = await InboxService.ack_message(
        db=db,
        message_id=message_id,
        user_id=body.user_id,
        status=body.status,
    )
    await db.commit()
    return {"message_id": msg_id, "status": status}
