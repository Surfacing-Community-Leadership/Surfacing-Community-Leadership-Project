import uuid
from datetime import datetime

from geoalchemy2 import Geography, WKBElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Event(Base):
    """One table serves both community gatherings and help requests —
    the shared 'invitation to show up'."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('gathering', 'help_request')", name="ck_events_kind"
        ),
        CheckConstraint(
            "visibility IN ('public', 'community', 'private')",
            name="ck_events_visibility",
        ),
        CheckConstraint(
            "status IN ('open', 'full', 'cancelled', 'completed')",
            name="ck_events_status",
        ),
        CheckConstraint("source IN ('user', 'imported')", name="ck_events_source"),
        Index("ix_events_location", "location", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(Text)
    # SET NULL: hosted events outlive a deleted host account, so people
    # who already RSVP'd don't lose the event out from under them.
    host_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    address: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visibility: Mapped[str] = mapped_column(Text, server_default=text("'public'"))
    capacity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    source: Mapped[str] = mapped_column(Text, server_default=text("'user'"))
    external_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )
