from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class ConnectionSummaryResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    avatar_key: str


class ConnectionRequestResponse(BaseModel):
    id: UUID
    requester_id: UUID
    addressee_id: UUID
    status: str
    created_at: datetime


class ConnectionCreateRequest(BaseModel):
    addressee_id: UUID


class ConnectionCreateResponse(BaseModel):
    id: UUID
    requester_id: UUID
    addressee_id: UUID
    status: str


class ConnectionUpdateRequest(BaseModel):
    status: str  # 'accepted'
