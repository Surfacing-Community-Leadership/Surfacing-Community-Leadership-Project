import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import Event, EventMessage, Profile, User
from app.routers.deps import (
    ACTIVE_PARTICIPANT_STATUSES,
    DB,
    CurrentUser,
    get_event_or_404,
    get_participation,
)
from app.schemas.message import MessageCreate, MessageCreated, MessageRead

router = APIRouter(prefix="/api/events/{event_id}/messages", tags=["messages"])


async def _require_participant(db, event: Event, user: User) -> None:
    """Messages are for the host and people actually tied to the event."""
    if event.host_id == user.id:
        return
    participation = await get_participation(db, event.id, user.id)
    if participation is None or participation.status not in ACTIVE_PARTICIPANT_STATUSES:
        raise HTTPException(
            status_code=403, detail="Only participants can use event messages"
        )


@router.get("", response_model=list[MessageRead])
async def list_messages(event_id: uuid.UUID, db: DB, user: CurrentUser):
    event = await get_event_or_404(db, event_id)
    await _require_participant(db, event, user)

    rows = (
        await db.execute(
            select(EventMessage, Profile.display_name)
            .join(Profile, Profile.user_id == EventMessage.sender_id)
            .where(EventMessage.event_id == event.id)
            .order_by(EventMessage.created_at)
        )
    ).all()
    return [
        MessageRead(
            id=m.id,
            sender_id=m.sender_id,
            display_name=name,
            body=m.body,
            created_at=m.created_at,
        )
        for m, name in rows
    ]


@router.post("", response_model=MessageCreated, status_code=201)
async def post_message(event_id: uuid.UUID, payload: MessageCreate, db: DB, user: CurrentUser):
    event = await get_event_or_404(db, event_id)
    await _require_participant(db, event, user)

    message = EventMessage(event_id=event.id, sender_id=user.id, body=payload.body)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return MessageCreated(
        id=message.id,
        event_id=message.event_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
    )
