import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrgFollow(Base):
    """Someone following a local organization.

    One-directional and needs no approval, unlike Connection — following a
    library is not a relationship the library has to accept. Only accounts with
    account_type='organization' can be followed; that's enforced in the router,
    since the check lives on profiles rather than here.
    """

    __tablename__ = "org_follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "org_id", name="uq_org_follows_pair"),
        CheckConstraint("follower_id <> org_id", name="ck_org_follows_not_self"),
        # Fanning out a new post reads every follower of one org.
        Index("ix_org_follows_org", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    follower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
