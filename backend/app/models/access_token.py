import uuid

from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.database import Base


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    """One row per live login session. The token column is an opaque random
    string (never a JWT), so deleting the row genuinely revokes the session.
    Expiry is enforced by created_at + the configured lifetime."""

    __tablename__ = "access_tokens"

    # The library base points its FK at a table named "user"; ours is "users".
    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="cascade"),
            nullable=False,
        )
