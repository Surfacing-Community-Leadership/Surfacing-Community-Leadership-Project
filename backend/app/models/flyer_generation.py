import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FlyerGeneration(Base):
    """One row per time someone asked the model for flyer copy.

    A table rather than an in-memory counter for two reasons. It survives a
    restart or a deploy, and it is correct when the server runs several worker
    processes — an in-process dict would give each worker its own count, so the
    real limit would silently become the cap times the number of workers.

    It doubles as an audit trail: if the free tier ever does get burned through,
    this says who did it and when, which a counter could not.

    Only *model* calls are recorded. Falling back to templated copy costs
    nothing, so it must not spend someone's daily allowance — otherwise an
    outage on Google's side would eat the quota of every user who tried.
    """

    __tablename__ = "flyer_generations"
    __table_args__ = (
        # The only query: how many has this person used today.
        Index("ix_flyer_generations_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # SET NULL, not CASCADE: deleting an event shouldn't refund the quota it
    # spent, or deleting your own event would be a way to reset the counter.
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
