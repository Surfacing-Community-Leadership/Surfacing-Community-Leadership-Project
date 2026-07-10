"""Shared dependencies and permission helpers used across routers."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_active_user
from app.core.database import get_db
from app.models import Block, Event, EventParticipant, Profile, User

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_active_user)]

# Participation states that still tie a person to an event.
ACTIVE_PARTICIPANT_STATUSES = ("invited", "going", "maybe", "attended")
# States that count toward capacity and reveal the address.
CONFIRMED_PARTICIPANT_STATUSES = ("going", "attended")


async def get_event_or_404(db: AsyncSession, event_id: uuid.UUID) -> Event:
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


async def get_participation(
    db: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID
) -> EventParticipant | None:
    return await db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == user_id,
        )
    )


async def get_my_community_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    return await db.scalar(select(Profile.community_id).where(Profile.user_id == user_id))


def blocked_counterparts(user_id: uuid.UUID):
    """Subquery of every user id that has a block with user_id, in either
    direction. Usable inside not_in() filters."""
    return select(
        case(
            (Block.blocker_id == user_id, Block.blocked_id),
            else_=Block.blocker_id,
        )
    ).where(or_(Block.blocker_id == user_id, Block.blocked_id == user_id))


async def user_can_view_event(db: AsyncSession, event: Event, user: User) -> bool:
    if event.host_id == user.id:
        return True
    # A block in either direction makes the host's events invisible.
    if event.host_id is not None and await blocked_either_way(db, user.id, event.host_id):
        return False
    if event.visibility == "public":
        return True
    if event.visibility == "community":
        if event.community_id is None:
            return False
        return await get_my_community_id(db, user.id) == event.community_id
    # private: only people with a participation row (invited or otherwise)
    return await get_participation(db, event.id, user.id) is not None


ALLOWED_STATUS_TRANSITIONS = {
    "open": {"full", "cancelled", "completed"},
    "full": {"open", "cancelled", "completed"},
    "cancelled": set(),  # terminal
    "completed": set(),  # terminal
}


async def require_event_view(db: AsyncSession, event: Event, user: User) -> None:
    if not await user_can_view_event(db, event, user):
        # 404 rather than 403: don't reveal that a private event exists.
        raise HTTPException(status_code=404, detail="Event not found")


async def blocked_either_way(
    db: AsyncSession, user_a: uuid.UUID, user_b: uuid.UUID
) -> bool:
    block = await db.scalar(
        select(Block).where(
            or_(
                (Block.blocker_id == user_a) & (Block.blocked_id == user_b),
                (Block.blocker_id == user_b) & (Block.blocked_id == user_a),
            )
        )
    )
    return block is not None
