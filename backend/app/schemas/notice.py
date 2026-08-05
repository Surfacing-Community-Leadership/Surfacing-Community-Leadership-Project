import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.notices import (
    EXPIRY_CHOICES_DAYS,
    MAX_BODY_CHARS,
    MAX_REPLY_CHARS,
    MIN_BODY_CHARS,
    NOTICE_CATEGORIES,
)
from app.schemas.common import LatLng

# Validated by membership rather than Literal[...]: the post types live in
# app.core.notices as the single source of truth, and Literal needs its members
# spelled out at import time, which would duplicate the list.
NoticeCategory = str


def _validate_category(value: str) -> str:
    if value not in NOTICE_CATEGORIES:
        raise ValueError(f"category must be one of {', '.join(NOTICE_CATEGORIES)}")
    return value


class NoticeCreate(BaseModel):
    category: NoticeCategory
    title: str = Field(min_length=1, max_length=140)
    # A floor as well as a ceiling: a board post with three words on it is a
    # feed post, and the point of the board is that entries say something.
    body: str = Field(min_length=MIN_BODY_CHARS, max_length=MAX_BODY_CHARS)
    place_hint: str | None = Field(None, max_length=200)
    # Optional pin on the map, for something area-bound.
    location: LatLng | None = None
    allow_direct_inquiries: bool = True
    # Omitted means the default window; the router caps how far out it may go.
    expires_at: datetime | None = None

    _check_category = field_validator("category")(_validate_category)


class NoticeUpdate(BaseModel):
    # Editable, but re-validated against the account type in the router — a
    # person must not be able to relabel their post as an official announcement.
    category: NoticeCategory | None = None
    title: str | None = Field(None, min_length=1, max_length=140)
    body: str | None = Field(None, min_length=MIN_BODY_CHARS, max_length=MAX_BODY_CHARS)
    place_hint: str | None = Field(None, max_length=200)
    location: LatLng | None = None
    # Explicit flag, because `location: None` in a PATCH is indistinguishable
    # from "not sent" once the payload is dumped with exclude_unset.
    clear_location: bool = False
    allow_direct_inquiries: bool | None = None
    expires_at: datetime | None = None
    # True marks it done ("the couch is gone"), False puts it back up.
    resolved: bool | None = None

    # Without this, an unknown or retired type slips past validation and lands on
    # the router's account-type check, which then reports "that post type is for
    # organization accounts" — true of neither, and misleading.
    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str | None) -> str | None:
        return None if value is None else _validate_category(value)


class NoticeSummary(BaseModel):
    """A notice as it appears in the board list."""

    id: uuid.UUID
    category: str
    title: str
    body: str
    place_hint: str | None
    location: LatLng | None = None
    author_id: uuid.UUID
    author_name: str | None
    author_is_org: bool
    author_verified: bool
    allow_direct_inquiries: bool
    expires_at: datetime
    resolved: bool
    created_at: datetime
    # Anonymous aggregate. There is deliberately no way to learn who starred —
    # not for the author either.
    stars: int = 0
    i_starred: bool = False
    # Only ever set for your own notices — nobody else learns who replied.
    reply_count: int | None = None
    # Whether the viewer has already replied, so the UI can say so.
    i_replied: bool = False


class NoticeReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_REPLY_CHARS)


class NoticeReplyRead(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str | None
    body: str
    created_at: datetime


class StarState(BaseModel):
    starred: bool
    stars: int


class BoardMeta(BaseModel):
    """What the board screen needs to render itself before showing any notices:
    which neighborhood it belongs to, what this account may post, and how much
    of its allowance is left."""

    community_id: uuid.UUID | None
    community_name: str | None
    categories: list[str]
    live_count: int
    max_live: int
    can_post: bool
    # Why posting is unavailable, when it is — the UI turns this into a prompt
    # rather than a dead button.
    blocked_reason: str | None = None
    expiry_choices_days: list[int] = list(EXPIRY_CHOICES_DAYS)
    default_expiry_days: int
    max_body_chars: int = MAX_BODY_CHARS
