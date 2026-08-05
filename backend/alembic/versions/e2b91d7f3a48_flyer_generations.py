"""flyer_generations — the durable per-user daily counter for AI flyer copy

A table rather than an in-process counter so the limit survives restarts and is
correct across worker processes.

Revision ID: e2b91d7f3a48
Revises: d1a7c46e9b25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2b91d7f3a48'
down_revision: Union[str, Sequence[str], None] = 'd1a7c46e9b25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flyer_generations",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL, not CASCADE: deleting an event must not refund the quota it
        # spent, or deleting your own event would reset the counter.
        sa.Column(
            "event_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_flyer_generations_user_created",
        "flyer_generations",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_flyer_generations_user_created", table_name="flyer_generations")
    op.drop_table("flyer_generations")
