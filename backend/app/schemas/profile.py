import uuid

from pydantic import BaseModel, ConfigDict, Field


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    avatar_key: str
    bio: str | None
    community_id: uuid.UUID | None
    show_attending: bool
    open_to_help: bool


class ProfilePublic(BaseModel):
    """What other users may see — no preference flags."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    avatar_key: str
    bio: str | None
    community_id: uuid.UUID | None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=80)
    avatar_key: str | None = None
    bio: str | None = Field(None, max_length=1000)
    community_id: uuid.UUID | None = None
    show_attending: bool | None = None
    open_to_help: bool | None = None


class InterestIds(BaseModel):
    interest_ids: list[uuid.UUID]
