"""add osm_ref to communities

Revision ID: 9a3f7c2b1e04
Revises: 5a4fdb5228c8
Create Date: 2026-07-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a3f7c2b1e04'
down_revision: Union[str, Sequence[str], None] = '5a4fdb5228c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("communities", sa.Column("osm_ref", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_communities_osm_ref", "communities", ["osm_ref"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_communities_osm_ref", "communities", type_="unique")
    op.drop_column("communities", "osm_ref")
