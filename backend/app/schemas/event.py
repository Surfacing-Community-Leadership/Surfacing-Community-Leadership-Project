from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class EventCreateRequest(BaseModel):
    kind: str  # 'gathering' | 'help_request'
    title: str
    description: str | None = None
    location: dict  # GeoJSON Point
    address: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    visibility: str = "public"  # 'public' | 'community' | 'private'
    capacity: int | None = None
    community_id: UUID | None = None
    interest_ids: list[UUID] | None = None


class EventUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    location: dict | None = None
    address: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visibility: str | None = None
    capacity: int | None = None
    status: str | None = None


class EventSummaryResponse(BaseModel):
    id: UUID
    kind: str
    title: str
    host_id: UUID | None
    location: dict
    starts_at: datetime
    visibility: str
    status: str
    distance_m: float | None = None


class EventDetailResponse(BaseModel):
    id: UUID
    kind: str
    host_id: UUID | None
    community_id: UUID | None
    title: str
    description: str | None
    location: dict
    address: str | None  # only populated for host/confirmed participants
    starts_at: datetime
    ends_at: datetime | None
    visibility: str
    capacity: int | None
    status: str
    source: str
    external_url: str | None
    participant_count: int


class ParticipantResponse(BaseModel):
    user_id: UUID
    display_name: str
    avatar_key: str
    status: str
    inviter_id: UUID | None


class RsvpRequest(BaseModel):
    status: str  # 'going' | 'maybe' | 'declined'


class RsvpResponse(BaseModel):
    event_id: UUID
    user_id: UUID
    status: str


class InviteRequest(BaseModel):
    user_id: UUID


class InviteResponse(BaseModel):
    event_id: UUID
    user_id: UUID
    status: str
    inviter_id: UUID | None


class EventMessageCreateRequest(BaseModel):
    body: str


class EventMessageResponse(BaseModel):
    id: UUID
    event_id: UUID
    sender_id: UUID
    body: str
    created_at: datetime
