"""add status to opportunities

Revision ID: a1b2c3d4e5f6
Revises: 1297e6a356eb
Create Date: 2026-07-19 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "1297e6a356eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("opportunities", sa.Column("status", sa.String(), nullable=True))
    op.execute("UPDATE opportunities SET status = 'SCREENING' WHERE status IS NULL")
    op.alter_column("opportunities", "status", nullable=False)
    op.create_index(
        op.f("ix_opportunities_status"),
        "opportunities",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_opportunities_status"), table_name="opportunities")
    op.drop_column("opportunities", "status")
