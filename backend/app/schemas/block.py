from pydantic import BaseModel
from uuid import UUID


class BlockResponse(BaseModel):
    blocked_id: UUID
    display_name: str


class BlockCreateRequest(BaseModel):
    blocked_id: UUID


class BlockCreateResponse(BaseModel):
    blocker_id: UUID
    blocked_id: UUID
