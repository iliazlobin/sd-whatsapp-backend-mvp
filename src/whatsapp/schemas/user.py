import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
