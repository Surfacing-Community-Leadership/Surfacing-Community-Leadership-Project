import uuid
from typing import Literal

from pydantic import BaseModel


class ParticipantRead(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_key: str
    status: str
    inviter_id: uuid.UUID | None


class RsvpPayload(BaseModel):
    status: Literal["going", "maybe", "declined"]


class RsvpRead(BaseModel):
    event_id: uuid.UUID
    user_id: uuid.UUID
    status: str


class InvitePayload(BaseModel):
    user_id: uuid.UUID


class InviteRead(BaseModel):
    event_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    inviter_id: uuid.UUID
