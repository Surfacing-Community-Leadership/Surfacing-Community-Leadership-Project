import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import and_, func, or_, select

from app.core.area_import import maybe_schedule_area_import
from app.core.geo import to_latlng, wkt_point
from app.core.notifications import notify
from app.models import Community, Event, EventParticipant, Interest, user_interests
from app.routers.deps import (
    ACTIVE_PARTICIPANT_STATUSES,
    ALLOWED_STATUS_TRANSITIONS,
    CONFIRMED_PARTICIPANT_STATUSES,
    DB,
    CurrentUser,
    blocked_counterparts,
    get_event_or_404,
    get_my_community_id,
    get_participation,
    not_ended_clause,
    require_event_view,
)
from app.schemas.event import EventCreate, EventDetail, EventKind, EventSummary, EventUpdate

router = APIRouter(prefix="/api/events", tags=["events"])


def _visibility_clause(user_id: uuid.UUID, my_community_id: uuid.UUID | None):
    """Which events this user is allowed to discover."""
    clauses = [
        Event.visibility == "public",
        Event.host_id == user_id,
        and_(
            Event.visibility == "private",
            Event.id.in_(
                select(EventParticipant.event_id).where(
                    EventParticipant.user_id == user_id
                )
            ),
        ),
    ]
    if my_community_id is not None:
        clauses.append(
            and_(
                Event.visibility == "community",
                Event.community_id == my_community_id,
            )
        )
    return or_(*clauses)


def _summary(event: Event, distance_m: float | None = None) -> EventSummary:
    return EventSummary(
        id=event.id,
        kind=event.kind,
        title=event.title,
        host_id=event.host_id,
        location=to_latlng(event.location),
        starts_at=event.starts_at,
        visibility=event.visibility,
        status=event.status,
        source=event.source,
        distance_m=round(distance_m, 1) if distance_m is not None else None,
        tag_slug=event.tag.slug if event.tag else None,
        tag_name=event.tag.name if event.tag else None,
    )


async def _resolve_tag(db, tag_id) -> Interest | None:
    """Validate the tag id and return the Interest so it can be assigned to the
    event's relationship directly — that keeps event.tag populated in memory,
    avoiding an async lazy-load after commit."""
    if tag_id is None:
        return None
    tag = await db.get(Interest, tag_id)
    if tag is None:
        raise HTTPException(status_code=422, detail="Unknown tag")
    return tag


async def _validate_community(db, community_id) -> None:
    if community_id is not None and await db.get(Community, community_id) is None:
        raise HTTPException(status_code=422, detail="Unknown community")


async def _require_own_community_id(db, user):
    """The host's community, for scoping a 'community only' event. Without it
    the event's community_id would be NULL and the visibility clause could
    never match, so the event would be invisible to the very people it targets."""
    community_id = await get_my_community_id(db, user.id)
    if community_id is None:
        raise HTTPException(
            status_code=422,
            detail="Join a community first to post a community-only event",
        )
    return community_id


@router.get("", response_model=list[EventSummary])
async def discover_events(
    db: DB,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[int, Query(gt=0, le=100_000)] = 5000,
    kind: EventKind | None = None,
    community_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    matching_interests: bool = False,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(gt=0, le=200)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The map query: visible events within radius_m of (lat, lng),
    nearest first. Defaults to upcoming events only. Optional tag_id filters to
    one category; matching_interests limits to categories the user follows."""
    # First view of a cold/stale area kicks off a background import of
    # external events for it — the map works anywhere, no per-city setup.
    maybe_schedule_area_import(background_tasks, lat, lng)
    my_community_id = await get_my_community_id(db, user.id)
    point = func.ST_GeogFromText(wkt_point(lat, lng))
    distance = func.ST_Distance(Event.location, point).label("distance_m")

    stmt = (
        select(Event, distance)
        .where(func.ST_DWithin(Event.location, point, radius_m))
        .where(_visibility_clause(user.id, my_community_id))
        # Events hosted by anyone you have a block with disappear entirely.
        # NULL hosts (account deleted) stay visible — not_in(NULL) is never true.
        .where(
            or_(
                Event.host_id.is_(None),
                Event.host_id.not_in(blocked_counterparts(user.id)),
            )
        )
        .where(Event.status.in_(("open", "full")))
        .order_by(distance)
        .limit(limit)
        .offset(offset)
    )
    if kind is not None:
        stmt = stmt.where(Event.kind == kind)
    if community_id is not None:
        stmt = stmt.where(Event.community_id == community_id)
    if tag_id is not None:
        stmt = stmt.where(Event.tag_id == tag_id)
    if matching_interests:
        # Only events tagged with a category this user follows.
        my_interests = select(user_interests.c.interest_id).where(
            user_interests.c.user_id == user.id
        )
        stmt = stmt.where(Event.tag_id.in_(my_interests))

    now = datetime.now(timezone.utc)
    if from_ is not None:
        # Explicit range query: filter strictly by start time.
        stmt = stmt.where(Event.starts_at >= from_)
    else:
        # Default map behavior: show events that haven't ended yet, so one
        # starting "now" doesn't disappear the moment it begins.
        stmt = stmt.where(not_ended_clause(now))
    if to is not None:
        stmt = stmt.where(Event.starts_at <= to)

    rows = (await db.execute(stmt)).all()
    return [_summary(event, dist) for event, dist in rows]


@router.post("", response_model=EventSummary, status_code=201)
async def create_event(payload: EventCreate, db: DB, user: CurrentUser):
    await _validate_community(db, payload.community_id)
    tag = await _resolve_tag(db, payload.tag_id)

    # A "community only" event is scoped to the host's own community.
    community_id = payload.community_id
    if payload.visibility == "community":
        community_id = await _require_own_community_id(db, user)

    event = Event(
        kind=payload.kind,
        host_id=user.id,
        community_id=community_id,
        tag=tag,  # assigning the object also sets tag_id and keeps it loaded
        title=payload.title,
        description=payload.description,
        location=wkt_point(payload.location.lat, payload.location.lng),
        address=payload.address,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        visibility=payload.visibility,
        capacity=payload.capacity,
    )
    db.add(event)
    await db.commit()
    # Reload the server-default status and the location as a proper geometry
    # (we assigned it as a WKT string). Naming attributes avoids re-expiring —
    # and async-lazy-loading — the tag relationship we assigned above.
    await db.refresh(event, attribute_names=["status", "location"])
    return _summary(event)


@router.get("/{event_id}", response_model=EventDetail)
async def read_event(event_id: uuid.UUID, db: DB, user: CurrentUser):
    event = await get_event_or_404(db, event_id)
    await require_event_view(db, event, user)

    participant_count = await db.scalar(
        select(func.count())
        .select_from(EventParticipant)
        .where(
            EventParticipant.event_id == event.id,
            EventParticipant.status.in_(CONFIRMED_PARTICIPANT_STATUSES),
        )
    )

    # The precise address is only for the host and confirmed participants;
    # everyone else gets the map point and community only. Imported events are
    # the exception: their venue is public information at the source already.
    show_address = event.host_id == user.id or event.source == "imported"
    if not show_address:
        participation = await get_participation(db, event.id, user.id)
        show_address = (
            participation is not None
            and participation.status in CONFIRMED_PARTICIPANT_STATUSES
        )

    return EventDetail(
        id=event.id,
        kind=event.kind,
        host_id=event.host_id,
        community_id=event.community_id,
        title=event.title,
        description=event.description,
        location=to_latlng(event.location),
        address=event.address if show_address else None,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        visibility=event.visibility,
        capacity=event.capacity,
        status=event.status,
        source=event.source,
        external_url=event.external_url,
        participant_count=participant_count,
        tag_id=event.tag_id,
        tag_slug=event.tag.slug if event.tag else None,
        tag_name=event.tag.name if event.tag else None,
    )


@router.patch("/{event_id}", response_model=EventSummary)
async def update_event(event_id: uuid.UUID, payload: EventUpdate, db: DB, user: CurrentUser):
    event = await get_event_or_404(db, event_id)
    if event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host may edit this event")

    updates = payload.model_dump(exclude_unset=True)

    # The tag is a relationship, not a plain column: resolve and assign the
    # object so event.tag stays consistent for the response. Popped so the
    # generic setattr loop below doesn't also try to set a "tag_id" attribute.
    if "tag_id" in updates:
        event.tag = await _resolve_tag(db, updates.pop("tag_id"))

    if "location" in updates and updates["location"] is not None:
        loc = payload.location
        updates["location"] = wkt_point(loc.lat, loc.lng)

    is_cancelling = updates.get("status") == "cancelled" and event.status != "cancelled"
    if "status" in updates and updates["status"] != event.status:
        if updates["status"] not in ALLOWED_STATUS_TRANSITIONS[event.status]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot change a {event.status} event to {updates['status']}",
            )

    # ends_at must still come after starts_at once the changes are applied
    # (validate against the merged values, since either may be updated alone).
    new_starts = updates.get("starts_at", event.starts_at)
    new_ends = updates.get("ends_at", event.ends_at)
    if new_ends is not None and new_ends <= new_starts:
        raise HTTPException(status_code=422, detail="End time must be after the start time")

    # Switching to community visibility scopes the event to the host's own
    # community (mirrors create) so it doesn't become invisible.
    new_visibility = updates.get("visibility", event.visibility)
    if new_visibility == "community" and event.community_id is None:
        event.community_id = await _require_own_community_id(db, user)

    for field, value in updates.items():
        setattr(event, field, value)

    # Tell everyone who RSVP'd that the event is off.
    if is_cancelling:
        attendee_ids = (
            await db.scalars(
                select(EventParticipant.user_id).where(
                    EventParticipant.event_id == event.id,
                    EventParticipant.status.in_(ACTIVE_PARTICIPANT_STATUSES),
                )
            )
        ).all()
        for attendee_id in attendee_ids:
            await notify(
                db, user_id=attendee_id, type="event_cancelled",
                actor_id=user.id, event_id=event.id,
            )

    await db.commit()
    # Reload location as a geometry if it was just set from a WKT string;
    # leaves the assigned tag relationship intact.
    await db.refresh(event, attribute_names=["location"])
    return _summary(event)


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    event = await get_event_or_404(db, event_id)
    if event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host may delete this event")

    # Cancelling notifies attendees; deleting must too — otherwise RSVP'd
    # neighbors plan around an event that silently ceased to exist. The
    # notification carries no event_id (the row is about to vanish); the
    # renderer's copy carries the meaning instead.
    attendee_ids = (
        await db.scalars(
            select(EventParticipant.user_id).where(
                EventParticipant.event_id == event.id,
                EventParticipant.status.in_(ACTIVE_PARTICIPANT_STATUSES),
            )
        )
    ).all()
    for attendee_id in attendee_ids:
        await notify(db, user_id=attendee_id, type="event_deleted", actor_id=user.id)

    await db.delete(event)
    await db.commit()
