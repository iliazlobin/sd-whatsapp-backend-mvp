import uuid

from pydantic import BaseModel, Field


class AckRequest(BaseModel):
    user_id: uuid.UUID
    status: str = Field(..., pattern="^(delivered|read)$")


class AckResponse(BaseModel):
    message_id: uuid.UUID
    status: str
