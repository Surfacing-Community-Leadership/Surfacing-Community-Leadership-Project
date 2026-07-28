import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# The kinds of local institution an org account can declare. Kept as a CHECK so
# the database itself rejects a typo'd category.
ORG_CATEGORIES = (
    "library",
    "school",
    "parks",
    "faith",
    "nonprofit",
    "government",
    "other",
)


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('person', 'organization')",
            name="ck_profiles_account_type",
        ),
        CheckConstraint(
            "org_category IS NULL OR org_category IN ('library', 'school', "
            "'parks', 'faith', 'nonprofit', 'government', 'other')",
            name="ck_profiles_org_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id", ondelete="SET NULL")
    )
    display_name: Mapped[str] = mapped_column(Text)
    avatar_key: Mapped[str] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    show_attending: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    open_to_help: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    # --- organization accounts -------------------------------------------
    # An account declares at signup whether it represents a person or a local
    # institution (library, school, parks dept, faith group, …). The *claim* is
    # self-service; the ✓ badge (User.org_verified) is not — see core/orgs.py.
    account_type: Mapped[str] = mapped_column(Text, server_default=text("'person'"))
    org_category: Mapped[str | None] = mapped_column(Text)
    # Public: residents see these on the org's profile, and an admin uses the
    # website as the evidence for granting verification.
    org_website: Mapped[str | None] = mapped_column(Text)
    org_phone: Mapped[str | None] = mapped_column(Text)
    org_address: Mapped[str | None] = mapped_column(Text)
    # Admin-only: who actually runs the account. Never serialized publicly.
    org_contact_name: Mapped[str | None] = mapped_column(Text)
    org_contact_role: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )
