from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select, update

from app.models import Event, HelpThanks, Notification, Profile
from app.routers.deps import DB, CurrentUser
from app.schemas.notification import NotificationRead, UnreadCount

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _render(
    n: Notification,
    actor_name: str | None,
    event_title: str | None,
    thanks_note: str | None = None,
    event_kind: str | None = None,
):
    """Compose the human sentence and click-target for a notification from its
    structured fields, so stored rows never hold stale text."""
    actor = actor_name or "Someone"
    title = event_title or "an event"
    event_link = f"/events/{n.event_id}" if n.event_id else None
    # A thank-you carries the neighbor's own words when they left any — read
    # live from help_thanks so an edited note is never stale here. An
    # organization confirming a volunteer shift reads differently from a
    # neighbour thanking you for a personal favour.
    if event_kind == "volunteer_work":
        thanks = f"{actor} confirmed you volunteered at {title}"
    else:
        thanks = f"{actor} said thanks for your help with {title}"
    if thanks_note:
        thanks = f'{thanks}: "{thanks_note}"'
    return {
        "event_invite": (f"{actor} invited you to {title}", event_link),
        # "RSVP'd", not "is going" — this fires for maybe as well as going.
        "event_rsvp": (f"{actor} RSVP'd to {title}", event_link),
        "event_cancelled": (f"{title} was cancelled", event_link),
        "event_deleted": (f"{actor} deleted an event you'd joined", None),
        "event_message": (f"{actor} posted in {title}", event_link),
        "connection_request": (f"{actor} wants to connect", "/connections"),
        "connection_accepted": (
            f"{actor} accepted your connection",
            f"/profile/{n.actor_id}" if n.actor_id else "/connections",
        ),
        "help_thanks": (thanks, event_link),
    }.get(n.type, ("You have a new notification", None))


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    db: DB,
    user: CurrentUser,
    limit: Annotated[int, Query(gt=0, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows = (
        await db.execute(
            select(
                Notification,
                Profile.display_name,
                Event.title,
                HelpThanks.note,
                Event.kind,
            )
            .outerjoin(Profile, Profile.user_id == Notification.actor_id)
            .outerjoin(Event, Event.id == Notification.event_id)
            # For a help_thanks the recipient of the notification *is* the
            # helper, so this pairs the row with the note left for them.
            .outerjoin(
                HelpThanks,
                (HelpThanks.event_id == Notification.event_id)
                & (HelpThanks.helper_id == Notification.user_id),
            )
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    out = []
    for n, actor_name, event_title, thanks_note, event_kind in rows:
        message, link = _render(n, actor_name, event_title, thanks_note, event_kind)
        out.append(
            NotificationRead(
                id=n.id,
                type=n.type,
                message=message,
                link=link,
                actor_id=n.actor_id,
                event_id=n.event_id,
                is_read=n.is_read,
                created_at=n.created_at,
            )
        )
    return out


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(db: DB, user: CurrentUser):
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
    )
    return UnreadCount(count=count or 0)


@router.post("/read", status_code=204)
async def mark_all_read(db: DB, user: CurrentUser) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
