"""notice board v2: more post types, map pins, stars, inquiry toggle

Four additions, all to an existing feature:
  * three more person post types (news, shoutout, blog)
  * an optional location, so an area-bound notice can drop a map pin
  * allow_direct_inquiries, so an author can close replies
  * notice_stars, for the anonymous aggregate count and post-of-the-day

Revision ID: c8d05f31b724
Revises: b6e4a2c80d13
"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8d05f31b724'
down_revision: Union[str, Sequence[str], None] = 'b6e4a2c80d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literals, not imports from app.core.notices: a migration describes the schema
# at *this* point in history and must not rewrite itself when the app's category
# list is next edited.
OLD_CATEGORIES = (
    "'giveaway', 'lost_found', 'recommendation', 'offer_help', "
    "'announcement', 'service_change'"
)
NEW_CATEGORIES = OLD_CATEGORIES + ", 'news', 'shoutout', 'blog'"


def upgrade() -> None:
    op.drop_constraint("ck_notices_category", "notices", type_="check")
    op.create_check_constraint(
        "ck_notices_category", "notices", f"category IN ({NEW_CATEGORIES})"
    )

    op.add_column(
        "notices",
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, spatial_index=False
            ),
            nullable=True,
        ),
    )
    # Partial: only a minority of notices are pinned, and a GiST index over
    # mostly-NULL rows is wasted pages.
    op.execute(
        "CREATE INDEX ix_notices_location ON notices USING gist (location) "
        "WHERE location IS NOT NULL"
    )

    op.add_column(
        "notices",
        sa.Column(
            "allow_direct_inquiries",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )

    op.create_table(
        "notice_stars",
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
        # The uniqueness IS the one-star-per-person rule.
        sa.UniqueConstraint("notice_id", "user_id", name="uq_notice_stars_user"),
    )
    op.create_index(
        "ix_notice_stars_notice_created", "notice_stars", ["notice_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_notice_stars_notice_created", table_name="notice_stars")
    op.drop_table("notice_stars")

    op.drop_column("notices", "allow_direct_inquiries")
    op.execute("DROP INDEX IF EXISTS ix_notices_location")
    op.drop_column("notices", "location")

    # Notices using a type that no longer exists would violate the restored
    # CHECK, so they go first.
    op.execute(
        "DELETE FROM notices WHERE category IN ('news', 'shoutout', 'blog')"
    )
    op.drop_constraint("ck_notices_category", "notices", type_="check")
    op.create_check_constraint(
        "ck_notices_category", "notices", f"category IN ({OLD_CATEGORIES})"
    )
