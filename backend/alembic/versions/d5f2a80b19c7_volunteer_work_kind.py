"""volunteer_work event kind

Organizations post volunteer work where an individual posts a help request: the
same "come lend a hand" shape, but institutional and many-to-one rather than one
neighbour asking another for a personal favour.

Only widens the CHECK — no existing rows change kind.

Revision ID: d5f2a80b19c7
Revises: c4a91e75d38f
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5f2a80b19c7'
down_revision: Union[str, Sequence[str], None] = 'c4a91e75d38f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_events_kind", "events", type_="check")
    op.create_check_constraint(
        "ck_events_kind",
        "events",
        "kind IN ('gathering', 'help_request', 'volunteer_work')",
    )


def downgrade() -> None:
    # Nothing sensible to convert them to — a volunteer shift is not a personal
    # favour — so they become plain gatherings rather than blocking the rollback.
    op.execute("UPDATE events SET kind = 'gathering' WHERE kind = 'volunteer_work'")
    op.drop_constraint("ck_events_kind", "events", type_="check")
    op.create_check_constraint(
        "ck_events_kind", "events", "kind IN ('gathering', 'help_request')"
    )
