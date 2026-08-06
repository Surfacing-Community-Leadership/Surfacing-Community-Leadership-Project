import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssistantTurn(Base):
    """One row per model call made by the guide, for the daily budget.

    A separate table from `flyer_generations` on purpose, even though the shape
    is identical. A flyer is one call; a guided conversation is five or ten. If
    they shared a counter, talking an event through would quietly eat the
    flyers someone had left for the week, and the two limits could never be
    tuned independently.

    Same reasoning as the flyer's table for why it is a table at all: it
    survives a restart and it is correct across worker processes, where an
    in-memory counter would give each worker its own and multiply the real cap.

    Nothing about *what* was said is recorded. The transcript lives in the
    person's browser; this is a count and a timestamp, so that the audit trail
    ("who spent the quota") does not become a log of half-formed ideas people
    decided not to post.
    """

    __tablename__ = "assistant_turns"
    __table_args__ = (
        # The only query: how many has this person used today.
        Index("ix_assistant_turns_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
