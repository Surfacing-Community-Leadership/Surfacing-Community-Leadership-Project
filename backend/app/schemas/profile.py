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
    # An org sees its own record, contact person included.
    account_type: str
    org_category: str | None
    org_website: str | None
    org_phone: str | None
    org_address: str | None
    org_contact_name: str | None
    org_contact_role: str | None


class ProfilePublic(BaseModel):
    """What other users may see — no preference flags, and for an organization
    no contact person (that's evidence for admins, not a public directory)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    avatar_key: str
    bio: str | None
    community_id: uuid.UUID | None
    account_type: str
    org_category: str | None
    org_website: str | None
    org_phone: str | None
    org_address: str | None
    # Whether the ✓ badge has been granted — lets a profile show
    # "Organization · unverified" until it has.
    verified: bool = False


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=80)
    avatar_key: str | None = None
    bio: str | None = Field(None, max_length=1000)
    community_id: uuid.UUID | None = None
    show_attending: bool | None = None
    open_to_help: bool | None = None


class InterestIds(BaseModel):
    interest_ids: list[uuid.UUID]


class TrustRecord(BaseModel):
    """A neighbor's public track record — plain verifiable counts plus the tier
    they add up to. Help *received* is deliberately absent."""

    verified: bool
    hosted: int
    attended: int
    helped: int
    tier: str
