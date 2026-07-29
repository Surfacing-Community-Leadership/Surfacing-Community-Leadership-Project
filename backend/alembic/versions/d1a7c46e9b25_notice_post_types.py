"""Rename the recommendation post type to question; retire offer_help

Two changes to the board's closed list of post types:
  * `recommendation` → `question` (same thing, plainer word)
  * `offer_help` retired

Existing rows are reclassified, never deleted — a migration that throws away
someone's writing to tidy an enum is doing the wrong thing. `offer_help` has no
exact survivor, so those posts become `blog`, which is the general-purpose
"take the space you need" type rather than a semantic claim about the content.

Revision ID: d1a7c46e9b25
Revises: c8d05f31b724
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd1a7c46e9b25'
down_revision: Union[str, Sequence[str], None] = 'c8d05f31b724'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literals, not imports from app.core.notices: a migration describes the schema
# at *this* point in history and must not rewrite itself when the app's type
# list is next edited.
OLD = (
    "'giveaway', 'lost_found', 'recommendation', 'offer_help', "
    "'announcement', 'service_change', 'news', 'shoutout', 'blog'"
)
NEW = (
    "'giveaway', 'lost_found', 'question', "
    "'announcement', 'service_change', 'news', 'shoutout', 'blog'"
)


def upgrade() -> None:
    # Constraint comes off FIRST. The old CHECK doesn't know 'question' yet, so
    # reclassifying rows while it is still in place fails on the very first row.
    op.drop_constraint("ck_notices_category", "notices", type_="check")

    op.execute("UPDATE notices SET category = 'question' WHERE category = 'recommendation'")
    op.execute("UPDATE notices SET category = 'blog' WHERE category = 'offer_help'")

    # Now the data satisfies the new CHECK, so it can be applied.
    op.create_check_constraint("ck_notices_category", "notices", f"category IN ({NEW})")


def downgrade() -> None:
    # Same ordering in reverse, for the same reason.
    op.drop_constraint("ck_notices_category", "notices", type_="check")
    op.execute("UPDATE notices SET category = 'recommendation' WHERE category = 'question'")
    op.create_check_constraint("ck_notices_category", "notices", f"category IN ({OLD})")
    # offer_help is NOT restored: the upgrade folded those rows into blog and
    # nothing recorded which ones they were. A downgrade leaves them as blog,
    # which is valid under the old CHECK too.
