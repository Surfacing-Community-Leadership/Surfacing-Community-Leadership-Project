from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import or_, select

from app.core.geo import to_latlng
from app.models import Event, EventParticipant
from app.routers.deps import DB, CurrentUser, not_ended_clause
from app.schemas.auth import UserMe
from app.schemas.event import EventSummary

router = APIRouter(prefix="/api/users", tags=["users"])


def _summary(e: Event, my_rsvp: str | None = None) -> EventSummary:
    return EventSummary(
        id=e.id,
        kind=e.kind,
        title=e.title,
        host_id=e.host_id,
        location=to_latlng(e.location),
        starts_at=e.starts_at,
        visibility=e.visibility,
        status=e.status,
        source=e.source,
        my_rsvp=my_rsvp,
        tag_slug=e.tag.slug if e.tag else None,
        tag_name=e.tag.name if e.tag else None,
    )


@router.get("/me", response_model=UserMe)
async def read_me(user: CurrentUser):
    return user


@router.get("/me/events", response_model=list[EventSummary])
async def my_events(user: CurrentUser, db: DB):
    """Events the current user created — gatherings and help requests alike,
    soonest first. Cancelled and already-ended events drop off."""
    now = datetime.now(timezone.utc)
    events = (
        await db.scalars(
            select(Event)
            .where(Event.host_id == user.id)
            .where(Event.status != "cancelled")
            .where(not_ended_clause(now))
            .order_by(Event.starts_at)
        )
    ).all()
    return [_summary(e) for e in events]


@router.get("/me/attending", response_model=list[EventSummary])
async def my_attending(user: CurrentUser, db: DB):
    """Events the current user has RSVP'd to as going or maybe (excluding their
    own), soonest first. Each row carries that RSVP. Cancelled and already-ended
    events drop off."""
    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Event, EventParticipant.status)
            .join(EventParticipant, EventParticipant.event_id == Event.id)
            .where(EventParticipant.user_id == user.id)
            .where(EventParticipant.status.in_(("going", "maybe")))
            # NULL hosts must be kept explicitly (SQL: NULL != x is not true):
            # imported events have no host, and they're the main thing people
            # RSVP to that they didn't create.
            .where(or_(Event.host_id.is_(None), Event.host_id != user.id))
            .where(Event.status != "cancelled")
            .where(not_ended_clause(now))
            .order_by(Event.starts_at)
        )
    ).all()
    return [_summary(event, my_rsvp=rsvp) for event, rsvp in rows]


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, db: DB) -> None:
    # Hard delete by design: profile, connections, blocks, participations and
    # messages cascade away; hosted events survive with host_id set to NULL.
    await db.delete(user)
    await db.commit()
