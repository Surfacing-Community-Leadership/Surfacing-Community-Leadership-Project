"""Creating notifications.

`notify` only stages a row (db.add) — it does NOT commit. Call it inside the
triggering action so the notification lands in the same transaction: if the
RSVP/invite/message rolls back, so does its notification, and vice versa.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, Notification


async def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    actor_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> None:
    """Stage a notification for `user_id`. Silently skips it when the actor is
    the recipient (no self-pings) or when the two have blocked each other."""
    if actor_id is not None and actor_id == user_id:
        return
    if actor_id is not None:
        blocked = await db.scalar(
            select(Block.blocker_id).where(
                or_(
                    (Block.blocker_id == user_id) & (Block.blocked_id == actor_id),
                    (Block.blocker_id == actor_id) & (Block.blocked_id == user_id),
                )
            )
        )
        if blocked is not None:
            return
    db.add(
        Notification(
            user_id=user_id, type=type, actor_id=actor_id, event_id=event_id
        )
    )
