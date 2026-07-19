"""allow event_deleted notifications; keep history when events are deleted

Revision ID: f2a6b9d4e781
Revises: e5b8d3c1f460
Create Date: 2026-07-19 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a6b9d4e781'
down_revision: Union[str, Sequence[str], None] = 'e5b8d3c1f460'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = ("'event_invite', 'event_rsvp', 'event_cancelled', "
             "'event_message', 'connection_request', 'connection_accepted'")
NEW_TYPES = ("'event_invite', 'event_rsvp', 'event_cancelled', 'event_deleted', "
             "'event_message', 'connection_request', 'connection_accepted'")


def upgrade() -> None:
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", f"type IN ({NEW_TYPES})"
    )
    # Notification history should outlive the event it references.
    op.drop_constraint(
        "notifications_event_id_fkey", "notifications", type_="foreignkey"
    )
    op.create_foreign_key(
        "notifications_event_id_fkey", "notifications", "events",
        ["event_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "notifications_event_id_fkey", "notifications", type_="foreignkey"
    )
    op.create_foreign_key(
        "notifications_event_id_fkey", "notifications", "events",
        ["event_id"], ["id"], ondelete="CASCADE",
    )
    op.execute("DELETE FROM notifications WHERE type = 'event_deleted'")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", f"type IN ({OLD_TYPES})"
    )
