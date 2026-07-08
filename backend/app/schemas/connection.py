import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConnectionCreate(BaseModel):
    addressee_id: uuid.UUID


class ConnectionUpdate(BaseModel):
    status: Literal["accepted"]


class ConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    status: str
    created_at: datetime


class ConnectionFriend(BaseModel):
    """An accepted connection, shown as the other person."""

    id: uuid.UUID  # the connection row id
    user_id: uuid.UUID
    display_name: str
    avatar_key: str
