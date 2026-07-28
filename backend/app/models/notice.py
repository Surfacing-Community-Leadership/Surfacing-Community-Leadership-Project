import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.notices import NOTICE_CATEGORIES

_CATEGORY_LIST = ", ".join(f"'{c}'" for c in NOTICE_CATEGORIES)


class Notice(Base):
    """A posting on a neighborhood's board.

    Separate from events on purpose. An event is an invitation with a time and a
    place you can stand in; a notice is information, and half of them have
    neither ("water main work on 5th all week"). Sharing the events table would
    mean carrying NOT NULL starts_at/location that don't apply, plus inheriting
    RSVPs, capacity and the trust tallies — every one of which would need a
    "unless it's a notice" carve-out.

    No geography column: the board is scoped by community_id, not by radius, so
    everyone in a neighborhood reads the same board rather than a personalized
    slice of one. A rough `place_hint` string covers "corner of 44th and 5th".
    """

    __tablename__ = "notices"
    __table_args__ = (
        CheckConstraint(f"category IN ({_CATEGORY_LIST})", name="ck_notices_category"),
        # The board query: one community's live notices, newest first.
        Index("ix_notices_community_expires", "community_id", "expires_at"),
        # Enforcing the per-author allowance means counting an author's live rows.
        Index("ix_notices_author", "author_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # CASCADE, unlike events' SET NULL: an event outlives its host because
    # people already RSVP'd and shouldn't lose it. Nobody depends on a notice
    # that way, and an unattributable notice is worse than no notice — being
    # answerable to your neighbors is what keeps a board civil.
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # NOT NULL: a notice with no board to sit on is unreachable by every query.
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    # Free text, not coordinates — "the bench by the playground" is more useful
    # to a neighbor than a pin, and notices never appear on the map.
    place_hint: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set when the author marks it done: the couch is gone, the cat came home.
    # Lets a notice stop lying without waiting out its expiry.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )


class NoticeReply(Base):
    """A private one-liner to whoever posted the notice.

    Only the author ever reads these. There are no public threads on the board
    by design — open comments are the specific mechanism that turns neighborhood
    feeds into argument venues — but "I'd like the couch" has to reach somebody,
    so it arrives as a notification instead.
    """

    __tablename__ = "notice_replies"
    __table_args__ = (
        # One reply per person per notice, so a single neighbor can't bury the
        # author's inbox. Sending again edits what you already said.
        UniqueConstraint("notice_id", "author_id", name="uq_notice_replies_author"),
        Index("ix_notice_replies_notice", "notice_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notices.id", ondelete="CASCADE")
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )
