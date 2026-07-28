import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.trust import MIN_REFLECTION_WORDS, word_count


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


class AttendancePayload(BaseModel):
    """Self-confirming you showed up. The reflection is required — it's what
    keeps the public 'attended' count from being farmable, and it stays private
    to its author."""

    reflection: str = Field(min_length=1, max_length=2000)

    @field_validator("reflection")
    @classmethod
    def _long_enough(cls, v: str) -> str:
        if word_count(v) < MIN_REFLECTION_WORDS:
            raise ValueError(
                f"Please write at least {MIN_REFLECTION_WORDS} words about how it went."
            )
        return v.strip()


class AttendanceRead(BaseModel):
    event_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    reflection: str


class ThanksPayload(BaseModel):
    """The person who asked for help confirming who turned up."""

    helper_id: uuid.UUID
    note: str | None = Field(None, max_length=500)


class ThanksRead(BaseModel):
    event_id: uuid.UUID
    helper_id: uuid.UUID
    note: str | None
