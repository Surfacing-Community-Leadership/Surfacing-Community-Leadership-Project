"""rename users.is_verified -> users.org_verified

The flag has always meant "a vetted local institution", but the name reads like
email verification — so every auth library that touches verification wants to
write to it. fastapi-users' verify router and its OAuth callback
(`is_verified_by_default`) both do, and either would silently hand the
organization badge to every signup.

Email confirmation lives in users.email_confirmed_at. This rename makes the two
impossible to confuse.

Revision ID: e7b104c95a23
Revises: d5f2a80b19c7
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7b104c95a23'
down_revision: Union[str, Sequence[str], None] = 'd5f2a80b19c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "is_verified", new_column_name="org_verified")


def downgrade() -> None:
    op.alter_column("users", "org_verified", new_column_name="is_verified")
