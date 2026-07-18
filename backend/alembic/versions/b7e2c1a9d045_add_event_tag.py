"""add single tag_id to events, retire event_interests

Revision ID: b7e2c1a9d045
Revises: 9a3f7c2b1e04
Create Date: 2026-07-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e2c1a9d045'
down_revision: Union[str, Sequence[str], None] = '9a3f7c2b1e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_events_tag_id", "events", "interests", ["tag_id"], ["id"],
        ondelete="SET NULL",
    )
    # Preserve existing categorization: pick one interest per event as its tag.
    op.execute(
        """
        UPDATE events SET tag_id = ei.interest_id
        FROM (
            SELECT DISTINCT ON (event_id) event_id, interest_id
            FROM event_interests
        ) ei
        WHERE ei.event_id = events.id
        """
    )
    # The many-to-many is superseded by the single tag.
    op.drop_table("event_interests")


def downgrade() -> None:
    op.create_table(
        "event_interests",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interest_id"], ["interests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "interest_id"),
    )
    op.execute(
        """
        INSERT INTO event_interests (event_id, interest_id)
        SELECT id, tag_id FROM events WHERE tag_id IS NOT NULL
        """
    )
    op.drop_constraint("fk_events_tag_id", "events", type_="foreignkey")
    op.drop_column("events", "tag_id")
