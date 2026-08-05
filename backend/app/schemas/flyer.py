import uuid
from datetime import datetime

from pydantic import BaseModel


class CopyOptionRead(BaseModel):
    headline: str
    blurb: str


class FlyerCopyRead(BaseModel):
    """Copy options for a flyer, plus what's left of today's allowance.

    `generated` says whether these came from the model or from the templated
    fallback. Reported honestly rather than hidden: the UI can label AI-written
    copy as such, and it means a Gemini outage is visible to us in logs and in
    tests without ever showing the user an error.
    """

    options: list[CopyOptionRead]
    generated: bool
    remaining_today: int
    daily_limit: int


class PublicEventRead(BaseModel):
    """An event as a stranger sees it, after scanning a flyer's QR code.

    This is the only unauthenticated view of an event in the app, so the field
    list *is* the privacy boundary. Everything absent here is absent on purpose:
    no host id, no coordinates, no participant list, no capacity, no RSVP state.

    `address` is present for a gathering or a volunteering shift — a host who
    chose public visibility and typed a venue wants people to find it — and is
    always withheld for a help request, where the address is somebody's home.
    """

    id: uuid.UUID
    kind: str
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime | None
    # The venue, or None when withheld. See the note above.
    address: str | None
    # The general area, always safe to show.
    neighborhood: str | None
    host_name: str | None
    tag_name: str | None
