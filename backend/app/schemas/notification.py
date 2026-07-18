import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: uuid.UUID
    type: str
    message: str  # a human sentence composed at read time
    link: str | None  # where clicking it should go, e.g. "/events/<id>"
    actor_id: uuid.UUID | None
    event_id: uuid.UUID | None
    is_read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    count: int
