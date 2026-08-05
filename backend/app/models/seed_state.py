import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SeedState(Base):
    """Which version of the demo seed this database currently holds.

    Exists to answer one question at deploy time: is the demo data in here the
    demo data this build expects? Before this, the deploy-time check was only
    "does the Sunset Park community exist", which meant that once a database had
    been seeded *once* it never picked up anything added to the seed afterwards —
    new features shipped with demo data that silently never appeared.

    One row, replaced on every seed. Not a history table; if an audit trail of
    seeding is ever wanted, that's a different thing with a different shape.
    """

    __tablename__ = "seed_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Bumped by hand in scripts/seed_demo.py whenever the seeded content changes.
    version: Mapped[int] = mapped_column(Integer)
    # Which slice of demo data this was, for a human reading the table.
    label: Mapped[str | None] = mapped_column(Text)
    seeded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
