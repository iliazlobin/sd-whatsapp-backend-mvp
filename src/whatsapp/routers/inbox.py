import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.database import get_session
from whatsapp.schemas.message import InboxSyncResponse
from whatsapp.services.inbox_service import InboxService

router = APIRouter(prefix="/v1/inbox", tags=["inbox"])


@router.get("", response_model=InboxSyncResponse)
async def sync_inbox(
    user_id: Annotated[uuid.UUID, Query(...)],
    since: Annotated[int, Query(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    messages, next_cursor = await InboxService.sync_inbox(
        db=db,
        user_id=user_id,
        since=since,
        limit=limit,
    )
    return InboxSyncResponse(messages=messages, next_cursor=next_cursor)
