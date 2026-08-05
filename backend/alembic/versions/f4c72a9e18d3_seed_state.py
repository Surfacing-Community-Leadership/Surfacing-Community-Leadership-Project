"""seed_state — records which version of the demo seed a database holds

Without this, the deploy-time seed only asked "does the demo community exist",
so a database seeded once never picked up demo data added later. Features
shipped with seeded content that silently never appeared.

Revision ID: f4c72a9e18d3
Revises: e2b91d7f3a48
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f4c72a9e18d3'
down_revision: Union[str, Sequence[str], None] = 'e2b91d7f3a48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seed_state",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column(
            "seeded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Deliberately NOT backfilled. An existing deployment has no recorded
    # version, which reads as "stale" — exactly right, since a database seeded
    # before this migration is missing everything added to the seed since.


def downgrade() -> None:
    op.drop_table("seed_state")
