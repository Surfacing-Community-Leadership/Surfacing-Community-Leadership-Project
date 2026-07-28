import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OAuthAccount(Base):
    """A third-party identity linked to a local user.

    Stored rather than matching on email alone so a provider identity is pinned
    to one account: if someone later changes their Google address, the link
    still holds, and a second provider can be added without ambiguity.
    """

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        # One local account per provider identity.
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_provider_account"
        ),
        # And at most one identity per provider per user.
        UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(Text)  # 'google'
    # The provider's stable subject id — not the email, which can change.
    provider_account_id: Mapped[str] = mapped_column(Text)
    # The address the provider reported at link time, kept for support/debugging.
    email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
