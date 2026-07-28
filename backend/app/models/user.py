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
    # NOTE: is_verified is the *organization* badge (a vetted local institution),
    # NOT email confirmation — those are deliberately separate signals. Proving
    # you can read an inbox is email_confirmed_at below; being a real library is
    # is_verified. Conflating them would hand the badge to every signup.
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_superuser: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Set when the address is proven reachable by clicking an emailed link.
    email_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
