"""organization accounts on profiles

Adds the organization claim (account_type + the org_* detail fields) to
profiles. Verification itself stays on users.is_verified, granted either by the
signup domain check (see app/core/orgs.py) or by an admin.

Revision ID: b8d3f10a4c62
Revises: a1c7e93b52d8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8d3f10a4c62'
down_revision: Union[str, Sequence[str], None] = 'a1c7e93b52d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORG_COLUMNS = (
    "org_category",
    "org_website",
    "org_phone",
    "org_address",
    "org_contact_name",
    "org_contact_role",
)


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "account_type",
            sa.Text(),
            server_default=sa.text("'person'"),
            nullable=False,
        ),
    )
    for name in ORG_COLUMNS:
        op.add_column("profiles", sa.Column(name, sa.Text(), nullable=True))

    op.create_check_constraint(
        "ck_profiles_account_type",
        "profiles",
        "account_type IN ('person', 'organization')",
    )
    op.create_check_constraint(
        "ck_profiles_org_category",
        "profiles",
        "org_category IS NULL OR org_category IN ('library', 'school', "
        "'parks', 'faith', 'nonprofit', 'government', 'other')",
    )
    # Org directories and filters read by type.
    op.create_index("ix_profiles_account_type", "profiles", ["account_type"])


def downgrade() -> None:
    op.drop_index("ix_profiles_account_type", table_name="profiles")
    op.drop_constraint("ck_profiles_org_category", "profiles", type_="check")
    op.drop_constraint("ck_profiles_account_type", "profiles", type_="check")
    for name in reversed(ORG_COLUMNS):
        op.drop_column("profiles", name)
    op.drop_column("profiles", "account_type")
