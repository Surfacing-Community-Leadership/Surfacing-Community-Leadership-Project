"""The guide — a few questions that end in a filled-in form.

  GET  /api/assistant/status   can this person use it, and how much is left
  POST /api/assistant/turn     the guide's next message and the draft so far

There is no create endpoint here, and that is the design. This router hands back
words; `POST /api/events` remains the only way an event comes into existence,
still reached by a person pressing the button on the ordinary form after reading
what it says. Every rule the events router enforces — the org-only volunteer
kind, community membership, the future start — keeps applying, unchanged and in
one place.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.assistant import (
    MAX_TURNS,
    AssistantBusy,
    AssistantUnavailable,
    Turn,
    configured,
    force_handoff,
    next_turn,
)
from app.core.config import settings
from app.models import AssistantTurn, Interest
from app.routers.deps import DB, CurrentUser, get_account_type
from app.schemas.assistant import AssistantStatus, DraftRead, TurnRead, TurnRequest

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# Which kinds each sort of account may be steered towards. The same split the
# frontend's kindsFor() makes and the events router enforces — repeated here so
# the guide never spends four questions building a draft the API would reject.
KINDS_BY_ACCOUNT = {
    "organization": ("gathering", "volunteer_work"),
    "person": ("gathering", "help_request"),
}


async def _used_today(db, user_id: uuid.UUID) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return (
        await db.scalar(
            select(func.count())
            .select_from(AssistantTurn)
            .where(AssistantTurn.user_id == user_id, AssistantTurn.created_at >= since)
        )
    ) or 0


@router.get("/status", response_model=AssistantStatus)
async def read_status(db: DB, user: CurrentUser):
    """Whether to offer the guide at all.

    Asked before the entry point is drawn, so a deployment without a Gemini key
    simply doesn't show it. A button that always fails is worse than no button.
    """
    limit = settings.assistant_daily_limit
    used = await _used_today(db, user.id)
    return AssistantStatus(
        available=configured() and used < limit,
        remaining_today=max(0, limit - used),
        daily_limit=limit,
        max_turns=MAX_TURNS,
    )


@router.post("/turn", response_model=TurnRead)
async def take_turn(body: TurnRequest, db: DB, user: CurrentUser):
    """The guide's next message, and the draft rebuilt from the whole
    conversation.

    Only ever fires on an explicit send. Nothing in the app calls this on page
    load, which is what keeps a free tier from draining while people browse.
    """
    if not configured():
        raise HTTPException(
            status_code=503,
            detail="The guide isn't available right now — the form works as usual.",
        )

    limit = settings.assistant_daily_limit
    used = await _used_today(db, user.id)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail="You've used the guide a lot today. The form is still right here.",
        )

    account_type = await get_account_type(db, user.id)
    allowed_kinds = KINDS_BY_ACCOUNT.get(account_type, KINDS_BY_ACCOUNT["person"])

    # The real categories, read fresh. The model picks from what exists rather
    # than from what it remembers, and anything else it says is discarded.
    tags = [
        (slug, name)
        for slug, name in (
            await db.execute(select(Interest.slug, Interest.name).order_by(Interest.name))
        ).all()
    ]

    transcript = [Turn(role=t.role, text=t.text) for t in body.transcript]

    try:
        guidance = await next_turn(
            transcript=transcript, allowed_kinds=allowed_kinds, tags=tags
        )
    except AssistantBusy:
        # The per-minute request quota is shared by the whole project, and one
        # conversation is several calls, so on a free tier this is the ordinary
        # failure rather than the exotic one. Saying "wait a moment" is both
        # true and useful; "unavailable" would send somebody away from a
        # feature that is about to work. Nothing is charged.
        raise HTTPException(
            status_code=429,
            detail="The guide is busy for a moment — send that again shortly.",
        ) from None
    except AssistantUnavailable:
        # Already logged with its cause in core.assistant. Nothing is charged:
        # a Gemini outage must not spend the budget of everyone who tried during
        # it, exactly as with the flyer.
        raise HTTPException(
            status_code=503,
            detail="The guide couldn't answer just now — the form works as usual.",
        ) from None

    db.add(AssistantTurn(user_id=user.id))
    await db.commit()
    used += 1

    # This reply plus the person's next message would reach the cap, so this is
    # the last thing the guide says. Offer what we have rather than asking
    # another question nobody can answer.
    exhausted = len(transcript) + 1 >= MAX_TURNS
    if exhausted and not guidance.ready:
        guidance = force_handoff(guidance)

    return TurnRead(
        reply=guidance.reply,
        draft=DraftRead(**vars(guidance.draft)),
        ready=guidance.ready,
        exhausted=exhausted,
        remaining_today=max(0, limit - used),
        daily_limit=limit,
    )
