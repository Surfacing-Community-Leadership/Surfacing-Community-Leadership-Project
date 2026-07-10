"""seed starter interests

Revision ID: 7c52bd870d32
Revises: a396a374f3fc
Create Date: 2026-07-08 13:17:15.720161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c52bd870d32'
down_revision: Union[str, Sequence[str], None] = 'a396a374f3fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STARTER_INTERESTS = [
    ("Sports & Fitness", "sports-fitness"),
    ("Outdoors & Nature", "outdoors-nature"),
    ("Gardening", "gardening"),
    ("Cooking & Food", "cooking-food"),
    ("Arts & Crafts", "arts-crafts"),
    ("Music", "music"),
    ("Books & Reading", "books-reading"),
    ("Games", "games"),
    ("Volunteering", "volunteering"),
    ("Kids & Family", "kids-family"),
    ("Seniors", "seniors"),
    ("Pets", "pets"),
    ("Technology", "technology"),
    ("Local History", "local-history"),
    ("Health & Wellness", "health-wellness"),
    ("Home Repair & DIY", "home-repair-diy"),
]


def upgrade() -> None:
    interests = sa.table(
        "interests",
        sa.column("name", sa.Text),
        sa.column("slug", sa.Text),
    )
    op.bulk_insert(
        interests,
        [{"name": name, "slug": slug} for name, slug in STARTER_INTERESTS],
    )


def downgrade() -> None:
    slugs = ", ".join(f"'{slug}'" for _, slug in STARTER_INTERESTS)
    op.execute(f"DELETE FROM interests WHERE slug IN ({slugs})")
