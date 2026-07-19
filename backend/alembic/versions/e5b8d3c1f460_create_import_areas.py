"""create import_areas tile-claim table

Revision ID: e5b8d3c1f460
Revises: d9c4e2f7a103
Create Date: 2026-07-19 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5b8d3c1f460'
down_revision: Union[str, Sequence[str], None] = 'd9c4e2f7a103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_areas",
        sa.Column("tile_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'running'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'done', 'failed')", name="ck_import_areas_status"
        ),
        sa.PrimaryKeyConstraint("tile_key"),
    )


def downgrade() -> None:
    op.drop_table("import_areas")
