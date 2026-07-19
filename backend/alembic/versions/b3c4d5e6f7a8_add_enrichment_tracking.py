"""add enrichment tracking

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 17:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('founders', sa.Column('last_enriched_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'enrichment_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('founder_id', sa.String(), nullable=False),
        sa.Column('stage', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('evidence_added', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence_before', sa.Float(), nullable=True),
        sa.Column('confidence_after', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['founder_id'], ['founders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_enrichment_runs_founder_id'), 'enrichment_runs', ['founder_id'], unique=False)
    op.create_index(op.f('ix_enrichment_runs_created_at'), 'enrichment_runs', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_enrichment_runs_created_at'), table_name='enrichment_runs')
    op.drop_index(op.f('ix_enrichment_runs_founder_id'), table_name='enrichment_runs')
    op.drop_table('enrichment_runs')
    op.drop_column('founders', 'last_enriched_at')
