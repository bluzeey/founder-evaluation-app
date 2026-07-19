"""Add source fields to founders.

Revision ID: 1297e6a356eb
Revises: f6cea5e9817c
Create Date: 2026-07-19 00:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1297e6a356eb"
down_revision: Union[str, None] = "f6cea5e9817c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("founders", sa.Column("source_reason", sa.Text(), nullable=True))
    op.add_column("founders", sa.Column("source_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("founders", "source_url")
    op.drop_column("founders", "source_reason")
