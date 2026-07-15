from fastapi import APIRouter
from sqlalchemy import select

from app.core.geo import to_latlng
from app.models import Event
from app.routers.deps import DB, CurrentUser
from app.schemas.auth import UserMe
from app.schemas.event import EventSummary

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserMe)
async def read_me(user: CurrentUser):
    return user


@router.get("/me/events", response_model=list[EventSummary])
async def my_events(user: CurrentUser, db: DB):
    """Everything the current user created — gatherings and help requests
    alike, in any status (so they can find cancelled/past ones too), newest
    first. Unlike the map, this is not filtered by time, distance, or status."""
    events = (
        await db.scalars(
            select(Event)
            .where(Event.host_id == user.id)
            .order_by(Event.created_at.desc())
        )
    ).all()
    return [
        EventSummary(
            id=e.id,
            kind=e.kind,
            title=e.title,
            host_id=e.host_id,
            location=to_latlng(e.location),
            starts_at=e.starts_at,
            visibility=e.visibility,
            status=e.status,
        )
        for e in events
    ]


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, db: DB) -> None:
    # Hard delete by design: profile, connections, blocks, participations and
    # messages cascade away; hosted events survive with host_id set to NULL.
    await db.delete(user)
    await db.commit()
