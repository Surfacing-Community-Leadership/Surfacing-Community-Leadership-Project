from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportArea(Base):
    """One row per map tile we've imported external events for. Doubles as a
    lock: claiming a tile (atomic upsert) is what grants the right to run its
    import, so a burst of users opening the same cold city triggers exactly
    one fetch. Tiles go stale on a TTL and get re-claimed for freshness."""

    __tablename__ = "import_areas"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'done', 'failed')", name="ck_import_areas_status"
        ),
    )

    # "40.50,-74.25" — the tile's SW corner, floored to the grid.
    tile_key: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'running'"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
