"""email confirmation

Adds users.email_confirmed_at — proof the address is reachable, kept separate
from is_verified (the organization badge) so confirming an email never grants
the ✓ mark on its own.

Existing accounts are left unconfirmed (NULL) rather than backfilled: nobody has
proven their address yet, and pretending otherwise would defeat the point. The
app stays usable while unconfirmed, so this is not disruptive.

Revision ID: c4a91e75d38f
Revises: b8d3f10a4c62
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4a91e75d38f'
down_revision: Union[str, Sequence[str], None] = 'b8d3f10a4c62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email_confirmed_at")
