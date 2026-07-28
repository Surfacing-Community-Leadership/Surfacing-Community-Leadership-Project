import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.notices import MAX_REPLY_CHARS, NOTICE_CATEGORIES

# Validated by membership rather than Literal[...]: the categories live in
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
    body: str = Field(min_length=10, max_length=2000)
    place_hint: str | None = Field(None, max_length=200)
    # Omitted means the default window; the router caps how far out it may go.
    expires_at: datetime | None = None

    _check_category = field_validator("category")(_validate_category)


class NoticeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=140)
    body: str | None = Field(None, min_length=10, max_length=2000)
    place_hint: str | None = Field(None, max_length=200)
    expires_at: datetime | None = None
    # True marks it done ("the couch is gone"), False puts it back up.
    resolved: bool | None = None


class NoticeSummary(BaseModel):
    """A notice as it appears in the board list."""

    id: uuid.UUID
    category: str
    title: str
    body: str
    place_hint: str | None
    author_id: uuid.UUID
    author_name: str | None
    author_is_org: bool
    author_verified: bool
    expires_at: datetime
    resolved: bool
    created_at: datetime
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
