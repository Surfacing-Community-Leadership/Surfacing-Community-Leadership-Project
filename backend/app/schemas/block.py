import uuid

from pydantic import BaseModel


class BlockCreate(BaseModel):
    blocked_id: uuid.UUID


class BlockRead(BaseModel):
    blocker_id: uuid.UUID
    blocked_id: uuid.UUID


class BlockedUser(BaseModel):
    blocked_id: uuid.UUID
    display_name: str
