"""add external_ref to events for imported-event upserts

Revision ID: d9c4e2f7a103
Revises: c3f1a8b6d922
Create Date: 2026-07-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd9c4e2f7a103'
down_revision: Union[str, Sequence[str], None] = 'c3f1a8b6d922'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("external_ref", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_events_external_ref", "events", ["external_ref"])


def downgrade() -> None:
    op.drop_constraint("uq_events_external_ref", "events", type_="unique")
    op.drop_column("events", "external_ref")
