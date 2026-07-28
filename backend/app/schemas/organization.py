import uuid

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    """An organization as it appears in a browse/follow list."""

    user_id: uuid.UUID
    display_name: str
    avatar_key: str
    bio: str | None
    org_category: str | None
    org_website: str | None
    verified: bool
    following: bool
    followers: int


class FollowState(BaseModel):
    following: bool
    followers: int
