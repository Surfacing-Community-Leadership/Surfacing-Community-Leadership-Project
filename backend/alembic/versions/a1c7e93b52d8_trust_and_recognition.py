"""trust and recognition: self-confirmed attendance + help thanks

Adds the two verifiable signals behind a profile's public track record:

* event_participants.attended_at / .reflection — an attendee self-confirms they
  showed up and writes a short reflection (the anti-farming friction).
* help_thanks — the person who asked for help confirms who actually helped,
  optionally with a note. This is the only source of the "helped" count.

Also widens the notifications type CHECK to allow 'help_thanks'.

Revision ID: a1c7e93b52d8
Revises: f2a6b9d4e781
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c7e93b52d8'
down_revision: Union[str, Sequence[str], None] = 'f2a6b9d4e781'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_participants",
        sa.Column("attended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "event_participants", sa.Column("reflection", sa.Text(), nullable=True)
    )

    op.create_table(
        "help_thanks",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "event_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "helper_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recipient_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("event_id", "helper_id", name="uq_help_thanks_event_helper"),
    )
    # The public tally reads by helper; the event page reads by event.
    op.create_index("ix_help_thanks_helper", "help_thanks", ["helper_id"])
    op.create_index("ix_help_thanks_event", "help_thanks", ["event_id"])

    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('event_invite', 'event_rsvp', 'event_cancelled', "
        "'event_deleted', 'event_message', 'connection_request', "
        "'connection_accepted', 'help_thanks')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE type = 'help_thanks'")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('event_invite', 'event_rsvp', 'event_cancelled', "
        "'event_deleted', 'event_message', 'connection_request', "
        "'connection_accepted')",
    )

    op.drop_index("ix_help_thanks_event", table_name="help_thanks")
    op.drop_index("ix_help_thanks_helper", table_name="help_thanks")
    op.drop_table("help_thanks")

    op.drop_column("event_participants", "reflection")
    op.drop_column("event_participants", "attended_at")
