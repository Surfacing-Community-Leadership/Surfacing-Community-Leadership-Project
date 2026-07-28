import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # The organization badge: a vetted local institution. Named org_verified,
    # not is_verified, because auth libraries reach for "is_verified" to mean
    # "email confirmed" — fastapi-users' verify router and its OAuth callback
    # both write to it — and granting this by that route would hand every signup
    # a badge. Email confirmation is email_confirmed_at, below.
    org_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_superuser: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Set when the address is proven reachable by clicking an emailed link.
    email_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
