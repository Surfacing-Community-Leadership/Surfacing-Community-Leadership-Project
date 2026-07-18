import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# The kinds of things that can generate a notification. Kept as a CHECK rather
# than a Python enum so the database itself rejects a typo'd type.
NOTIFICATION_TYPES = (
    "event_invite",       # someone invited you to their event
    "event_rsvp",         # someone RSVP'd to an event you host
    "event_cancelled",    # an event you're attending was cancelled
    "event_message",      # a new message in an event you're part of
    "connection_request", # someone asked to connect
    "connection_accepted",# someone accepted your connection request
)


class Notification(Base):
    """One row per thing a user should know about. Stores structured refs
    (type + actor + event) rather than a frozen sentence, so the message and
    its links are composed live at read time and never go stale."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('event_invite', 'event_rsvp', 'event_cancelled', "
            "'event_message', 'connection_request', 'connection_accepted')",
            name="ck_notifications_type",
        ),
        # Newest-first listing and the unread-count both filter by recipient.
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # The recipient. CASCADE: notifications die with the account.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(Text)
    # Who triggered it (SET NULL so a deleted account leaves the row readable).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # The event it's about (NULL for connection notifications). CASCADE: if the
    # event is deleted, notifications about it go too rather than dangle.
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    is_read: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
