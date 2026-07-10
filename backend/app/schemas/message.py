import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageRead(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    display_name: str
    body: str
    created_at: datetime


class MessageCreated(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime
