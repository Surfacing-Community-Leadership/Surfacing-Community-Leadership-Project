"""Flyer copy, and the one public view of an event.

Two endpoints that belong together because the flyer is useless without the
page its QR code points at.

  POST /api/events/{id}/flyer-copy   host-only, capped, calls Gemini
  GET  /api/public/events/{id}       NO AUTH — what a stranger sees after
                                     scanning the flyer

The public endpoint is the only unauthenticated read of app data anywhere in
this codebase, so it is written to be boring: public-visibility events only, a
hand-listed set of fields, and no branch that could widen either.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.config import settings
from app.core.flyer import flyer_copy
from app.models import Community, Event, FlyerGeneration, Profile
from app.routers.deps import DB, CurrentUser
from app.schemas.flyer import CopyOptionRead, FlyerCopyRead, PublicEventRead

router = APIRouter(tags=["flyers"])

# A flyer is a public artefact, so it only makes sense for an event that people
# are actually allowed to turn up to. A private invite-only event is excluded on
# purpose: printing a QR to a publicly-readable page would quietly undo the
# visibility its host chose.
FLYERABLE_VISIBILITY = ("public", "community")

# Kinds whose address is a venue rather than someone's home.
VENUE_KINDS = ("gathering", "volunteer_work")


async def _used_today(db, user_id: uuid.UUID) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return (
        await db.scalar(
            select(func.count())
            .select_from(FlyerGeneration)
            .where(FlyerGeneration.user_id == user_id, FlyerGeneration.created_at >= since)
        )
    ) or 0


@router.post("/api/events/{event_id}/flyer-copy", response_model=FlyerCopyRead)
async def create_flyer_copy(event_id: uuid.UUID, db: DB, user: CurrentUser):
    """Headline and blurb options for this event's flyer.

    Only ever runs on an explicit button press — nothing in the app calls this
    on page load, which is what keeps the free tier from draining on its own.
    """
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can make a flyer")
    if event.visibility not in FLYERABLE_VISIBILITY:
        raise HTTPException(
            status_code=409,
            detail="A private event can't have a flyer — its page would be public",
        )

    limit = settings.flyer_daily_limit
    used = await _used_today(db, user.id)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"That's {limit} flyers today. Try again tomorrow.",
        )

    host_name = await db.scalar(
        select(Profile.display_name).where(Profile.user_id == event.host_id)
    )
    neighborhood = (
        await db.scalar(select(Community.name).where(Community.id == event.community_id))
        if event.community_id
        else None
    )

    # Note what is not passed: event.address. The signature of flyer_copy has no
    # parameter for it, so this cannot leak one even by mistake.
    copy = await flyer_copy(
        title=event.title,
        description=event.description,
        host_name=host_name,
        neighborhood=neighborhood,
        starts_at=event.starts_at,
        kind=event.kind,
    )

    # Only a real model call spends allowance. Templated copy is free, so a
    # Gemini outage must not eat the quota of everyone who tried during it.
    if copy.generated:
        db.add(FlyerGeneration(user_id=user.id, event_id=event.id))
        await db.commit()
        used += 1

    return FlyerCopyRead(
        options=[CopyOptionRead(headline=o.headline, blurb=o.blurb) for o in copy.options],
        generated=copy.generated,
        remaining_today=max(0, limit - used),
        daily_limit=limit,
    )


# ---- the public page behind the QR code -------------------------------------
#
# Deliberately NOT under /api/events: that router's dependencies assume an
# authenticated user, and a public route living beside them is exactly how one
# accidentally inherits a `CurrentUser` and stops being public — or worse,
# doesn't, and inherits something else.


@router.get("/api/public/events/{event_id}", response_model=PublicEventRead)
async def read_public_event(event_id: uuid.UUID, db: DB):
    """What a stranger sees after scanning a flyer. No authentication.

    Note the signature: `db` but no `user`. `DB` is only the database session —
    `CurrentUser` is what requires a login — so this route is public by virtue of
    what it does not ask for.

    Public-visibility events only. A community-only event can carry a flyer (its
    neighbours may print one) but its page is not readable by the open internet,
    so scanning it prompts a sign-in instead.
    """
    event = await db.get(Event, event_id)
    # One response for "no such event", "not public" and "cancelled": a stranger
    # probing ids should not be able to tell them apart.
    if event is None or event.visibility != "public" or event.status == "cancelled":
        raise HTTPException(status_code=404, detail="Event not found")

    host_name = (
        await db.scalar(
            select(Profile.display_name).where(Profile.user_id == event.host_id)
        )
        if event.host_id
        else None
    )
    neighborhood = (
        await db.scalar(
            select(Community.name).where(Community.id == event.community_id)
        )
        if event.community_id
        else None
    )

    return PublicEventRead(
        id=event.id,
        kind=event.kind,
        title=event.title,
        description=event.description,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        # A help request's address is a home. Never public, whatever the
        # visibility setting says.
        address=event.address if event.kind in VENUE_KINDS else None,
        neighborhood=neighborhood,
        host_name=host_name,
        tag_name=event.tag.name if event.tag else None,
    )
