"""notices + notice_replies, notice_reply notifications, notice reports

The board is scoped by community_id rather than by radius, so there is no
geography column here and nothing for PostGIS to index — everyone in a
neighborhood reads the same board.

Revision ID: b6e4a2c80d13
Revises: a92f4c1d7e58
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b6e4a2c80d13'
down_revision: Union[str, Sequence[str], None] = 'a92f4c1d7e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kept as a literal rather than imported from app.core.notices: a migration has
# to describe the schema at *this* point in history, and would otherwise start
# rewriting itself the day someone edits the category list.
CATEGORIES = (
    "'giveaway', 'lost_found', 'recommendation', 'offer_help', "
    "'announcement', 'service_change'"
)

TYPES = (
    "'event_invite', 'event_rsvp', 'event_cancelled', 'event_deleted', "
    "'event_message', 'connection_request', 'connection_accepted', "
    "'help_thanks', 'org_event'"
)


def upgrade() -> None:
    op.create_table(
        "notices",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "author_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "community_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("communities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("place_hint", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"category IN ({CATEGORIES})", name="ck_notices_category"),
    )
    op.create_index(
        "ix_notices_community_expires", "notices", ["community_id", "expires_at"]
    )
    op.create_index("ix_notices_author", "notices", ["author_id"])

    op.create_table(
        "notice_replies",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "notice_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("notice_id", "author_id", name="uq_notice_replies_author"),
    )
    op.create_index(
        "ix_notice_replies_notice", "notice_replies", ["notice_id", "created_at"]
    )

    # A reply notification needs somewhere to point: notifications only carried
    # an event_id before this.
    op.add_column(
        "notifications",
        sa.Column(
            "notice_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", f"type IN ({TYPES}, 'notice_reply')"
    )

    # Notices become a reportable target alongside users and events.
    op.add_column(
        "reports",
        sa.Column(
            "reported_notice_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.drop_constraint("ck_reports_has_target", "reports", type_="check")
    op.create_check_constraint(
        "ck_reports_has_target",
        "reports",
        "reported_user_id IS NOT NULL OR reported_event_id IS NOT NULL "
        "OR reported_notice_id IS NOT NULL",
    )


def downgrade() -> None:
    # Reports that only ever pointed at a notice would violate the restored
    # CHECK, so they go before it is put back.
    op.execute(
        "DELETE FROM reports WHERE reported_user_id IS NULL "
        "AND reported_event_id IS NULL"
    )
    op.drop_constraint("ck_reports_has_target", "reports", type_="check")
    op.create_check_constraint(
        "ck_reports_has_target",
        "reports",
        "reported_user_id IS NOT NULL OR reported_event_id IS NOT NULL",
    )
    op.drop_column("reports", "reported_notice_id")

    op.execute("DELETE FROM notifications WHERE type = 'notice_reply'")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", f"type IN ({TYPES})"
    )
    op.drop_column("notifications", "notice_id")

    op.drop_index("ix_notice_replies_notice", table_name="notice_replies")
    op.drop_table("notice_replies")
    op.drop_index("ix_notices_author", table_name="notices")
    op.drop_index("ix_notices_community_expires", table_name="notices")
    op.drop_table("notices")
