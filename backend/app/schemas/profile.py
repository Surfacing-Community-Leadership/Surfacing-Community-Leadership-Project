from pydantic import BaseModel
from uuid import UUID


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    avatar_key: str
    bio: str | None
    community_id: UUID | None
    show_attending: bool
    open_to_help: bool


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    avatar_key: str | None = None
    bio: str | None = None
    community_id: UUID | None = None
    show_attending: bool | None = None
    open_to_help: bool | None = None


class PublicProfileResponse(BaseModel):
    user_id: UUID
    display_name: str
    avatar_key: str
    bio: str | None
    community_id: UUID | None


class InterestSelectionRequest(BaseModel):
    interest_ids: list[UUID]


class InterestSelectionResponse(BaseModel):
    interest_ids: list[UUID]
