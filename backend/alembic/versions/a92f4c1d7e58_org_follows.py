"""org_follows + org_event notification type

Following an organization is one-directional and needs no approval, so it gets
its own table rather than reusing connections.

Revision ID: a92f4c1d7e58
Revises: f3c86d21ab40
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a92f4c1d7e58'
down_revision: Union[str, Sequence[str], None] = 'f3c86d21ab40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPES = (
    "'event_invite', 'event_rsvp', 'event_cancelled', 'event_deleted', "
    "'event_message', 'connection_request', 'connection_accepted', 'help_thanks'"
)


def upgrade() -> None:
    op.create_table(
        "org_follows",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "follower_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
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
        sa.UniqueConstraint("follower_id", "org_id", name="uq_org_follows_pair"),
        sa.CheckConstraint("follower_id <> org_id", name="ck_org_follows_not_self"),
    )
    op.create_index("ix_org_follows_org", "org_follows", ["org_id"])

    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", f"type IN ({TYPES}, 'org_event')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE type = 'org_event'")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", f"type IN ({TYPES})"
    )

    op.drop_index("ix_org_follows_org", table_name="org_follows")
    op.drop_table("org_follows")
