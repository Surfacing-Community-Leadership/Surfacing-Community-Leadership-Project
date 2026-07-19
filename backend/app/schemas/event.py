import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import LatLng

EventKind = Literal["gathering", "help_request"]
EventVisibility = Literal["public", "community", "private"]
EventStatus = Literal["open", "full", "cancelled", "completed"]


class EventCreate(BaseModel):
    kind: EventKind
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    location: LatLng
    address: str | None = Field(None, max_length=500)
    starts_at: datetime
    ends_at: datetime | None = None
    visibility: EventVisibility = "public"
    capacity: int | None = Field(None, gt=0)
    community_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def ends_after_start(self):
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    location: LatLng | None = None
    address: str | None = Field(None, max_length=500)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visibility: EventVisibility | None = None
    capacity: int | None = Field(None, gt=0)
    tag_id: uuid.UUID | None = None
    status: EventStatus | None = None


class EventSummary(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    host_id: uuid.UUID | None
    location: LatLng
    starts_at: datetime
    visibility: str
    status: str
    # "user" or "imported" — imported events get an ↗ marker in lists.
    source: str = "user"
    distance_m: float | None = None
    # The viewer's own RSVP ("going"/"maybe"), set only by the "going to" list.
    my_rsvp: str | None = None
    # The event's single category, used to pick the map pin's icon.
    tag_slug: str | None = None
    tag_name: str | None = None


class EventDetail(BaseModel):
    id: uuid.UUID
    kind: str
    host_id: uuid.UUID | None
    community_id: uuid.UUID | None
    title: str
    description: str | None
    location: LatLng
    address: str | None  # only revealed to host + confirmed participants
    starts_at: datetime
    ends_at: datetime | None
    visibility: str
    capacity: int | None
    status: str
    source: str
    external_url: str | None
    participant_count: int
    tag_id: uuid.UUID | None = None
    tag_slug: str | None = None
    tag_name: str | None = None
