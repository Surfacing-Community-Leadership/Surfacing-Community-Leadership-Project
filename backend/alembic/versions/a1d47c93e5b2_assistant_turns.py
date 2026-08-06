"""assistant_turns — the guide's per-person daily budget

A separate table from flyer_generations even though the shape matches: a flyer
is one model call, a guided conversation is five or ten, so sharing a counter
would mean talking one event through spent a week of someone's flyers.

Counts and timestamps only. What was said stays in the person's browser.

Revision ID: a1d47c93e5b2
Revises: f4c72a9e18d3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1d47c93e5b2'
down_revision: Union[str, Sequence[str], None] = 'f4c72a9e18d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_turns",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # The only query this table serves: how many turns has this person used
    # since yesterday.
    op.create_index(
        "ix_assistant_turns_user_created", "assistant_turns", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_turns_user_created", table_name="assistant_turns")
    op.drop_table("assistant_turns")
