import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HelpThanks(Base):
    """One neighbor confirming that another actually helped them.

    This is the *only* source of the public "helped" count. It can't be
    self-declared: the row is written by the person who asked for help, about
    the person who turned up. That makes the number on a profile something a
    stranger can reasonably trust when deciding whether to accept a hand.
    """

    __tablename__ = "help_thanks"
    __table_args__ = (
        # One thanks per helper per request, so a count can't be inflated by
        # thanking the same person repeatedly.
        UniqueConstraint("event_id", "helper_id", name="uq_help_thanks_event_helper"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    # The neighbor being thanked — their public "helped" tally counts these.
    helper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # The person who asked for help and is confirming it happened.
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
