import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, or_, select

from app.core.notifications import notify
from app.models import Connection, Event, EventParticipant, Notification, Profile, User
from app.routers.deps import (
    ACTIVE_PARTICIPANT_STATUSES,
    CONFIRMED_PARTICIPANT_STATUSES,
    DB,
    CurrentUser,
    blocked_counterparts,
    blocked_either_way,
    get_event_or_404,
    get_participation,
    require_event_view,
)
from app.schemas.participant import (
    InvitePayload,
    InviteRead,
    ParticipantRead,
    RsvpPayload,
    RsvpRead,
)

router = APIRouter(prefix="/api/events/{event_id}", tags=["participation"])


async def _confirmed_count(db, event_id) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(EventParticipant)
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status.in_(CONFIRMED_PARTICIPANT_STATUSES),
        )
    )


async def _sync_full_status(db, event: Event) -> None:
    """Keep the open⇄full status in step with capacity: filling the last seat
    flips the event to 'full' (so the map shows it honestly), and a withdrawal
    reopens it. Never touches cancelled/completed, and capacity-less events
    are always just open."""
    if event.capacity is None or event.status not in ("open", "full"):
        return
    confirmed = await _confirmed_count(db, event.id)
    if confirmed >= event.capacity and event.status == "open":
        event.status = "full"
    elif confirmed < event.capacity and event.status == "full":
        event.status = "open"


@router.get("/participants", response_model=list[ParticipantRead])
async def list_participants(
    event_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
    limit: Annotated[int, Query(gt=0, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    event = await get_event_or_404(db, event_id)
    await require_event_view(db, event, user)

    rows = (
        await db.execute(
            select(EventParticipant, Profile)
            .join(Profile, Profile.user_id == EventParticipant.user_id)
            .where(EventParticipant.event_id == event.id)
            # Hide anyone you have a block with (either direction) — e.g. in an
            # event you both joined that a third person hosts.
            .where(EventParticipant.user_id.not_in(blocked_counterparts(user.id)))
            .order_by(EventParticipant.created_at)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [
        ParticipantRead(
            user_id=p.user_id,
            display_name=profile.display_name,
            avatar_key=profile.avatar_key,
            status=p.status,
            inviter_id=p.inviter_id,
        )
        for p, profile in rows
    ]


@router.put("/rsvp", response_model=RsvpRead)
async def set_rsvp(event_id: uuid.UUID, payload: RsvpPayload, db: DB, user: CurrentUser):
    event = await get_event_or_404(db, event_id)
    await require_event_view(db, event, user)
    if event.status in ("cancelled", "completed"):
        raise HTTPException(status_code=409, detail="This event is no longer open")

    participation = await get_participation(db, event.id, user.id)

    if payload.status == "going":
        already_confirmed = (
            participation is not None
            and participation.status in CONFIRMED_PARTICIPANT_STATUSES
        )
        if event.capacity is not None and not already_confirmed:
            if await _confirmed_count(db, event.id) >= event.capacity:
                raise HTTPException(status_code=409, detail="This event is full")

    if participation is None:
        participation = EventParticipant(
            event_id=event.id, user_id=user.id, status=payload.status
        )
        db.add(participation)
    else:
        participation.status = payload.status

    # Let the host know when someone's coming (not on a "declined") — but only
    # once per unread stretch, so toggling going/maybe doesn't ping them again.
    if event.host_id is not None and payload.status in ("going", "maybe"):
        already_pinged = await db.scalar(
            select(Notification.id).where(
                Notification.user_id == event.host_id,
                Notification.actor_id == user.id,
                Notification.event_id == event.id,
                Notification.type == "event_rsvp",
                Notification.is_read.is_(False),
            )
        )
        if already_pinged is None:
            await notify(
                db, user_id=event.host_id, type="event_rsvp",
                actor_id=user.id, event_id=event.id,
            )

    # Filling the last seat flips the event to 'full'; downgrading a confirmed
    # RSVP (going -> maybe/declined) can reopen it.
    await _sync_full_status(db, event)
    await db.commit()
    return RsvpRead(event_id=event.id, user_id=user.id, status=payload.status)


@router.delete("/rsvp", status_code=204)
async def withdraw_rsvp(event_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    event = await get_event_or_404(db, event_id)
    participation = await get_participation(db, event.id, user.id)
    if participation is None:
        raise HTTPException(status_code=404, detail="You are not participating")
    await db.delete(participation)
    await _sync_full_status(db, event)  # a freed seat can reopen a full event
    await db.commit()


@router.post("/invites", response_model=InviteRead, status_code=201)
async def invite_user(event_id: uuid.UUID, payload: InvitePayload, db: DB, user: CurrentUser):
    event = await get_event_or_404(db, event_id)
    await require_event_view(db, event, user)

    # Only people actually tied to the event may pull others in.
    if event.host_id != user.id:
        my_participation = await get_participation(db, event.id, user.id)
        if my_participation is None or my_participation.status not in ACTIVE_PARTICIPANT_STATUSES:
            raise HTTPException(status_code=403, detail="Join the event before inviting others")

    invitee = await db.get(User, payload.user_id)
    if invitee is None:
        raise HTTPException(status_code=404, detail="User not found")

    if await blocked_either_way(db, user.id, payload.user_id):
        raise HTTPException(status_code=403, detail="You cannot invite this user")

    connection = await db.scalar(
        select(Connection).where(
            Connection.status == "accepted",
            or_(
                and_(
                    Connection.requester_id == user.id,
                    Connection.addressee_id == payload.user_id,
                ),
                and_(
                    Connection.requester_id == payload.user_id,
                    Connection.addressee_id == user.id,
                ),
            ),
        )
    )
    if connection is None:
        raise HTTPException(
            status_code=403, detail="You can only invite your accepted connections"
        )

    if await get_participation(db, event.id, payload.user_id) is not None:
        raise HTTPException(
            status_code=409, detail="This user is already invited or participating"
        )

    invite = EventParticipant(
        event_id=event.id,
        user_id=payload.user_id,
        inviter_id=user.id,
        status="invited",
    )
    db.add(invite)
    await notify(
        db, user_id=payload.user_id, type="event_invite",
        actor_id=user.id, event_id=event.id,
    )
    await db.commit()
    return InviteRead(
        event_id=event.id, user_id=payload.user_id, status="invited", inviter_id=user.id
    )
