"""Add private owner authentication tables without changing business data.

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "owner_auth_identity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
        sa.CheckConstraint("id = 1", name="ck_owner_auth_single_owner"),
    )
    op.create_table(
        "owner_auth_states",
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(43), nullable=False),
        sa.Column("pkce_verifier", sa.String(43), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index("ix_owner_auth_states_expires_at", "owner_auth_states", ["expires_at"])
    op.create_table(
        "owner_auth_sessions",
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["owner_auth_identity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_hash"),
    )
    op.create_index("ix_owner_auth_sessions_expires_at", "owner_auth_sessions", ["expires_at"])


def downgrade():
    op.drop_table("owner_auth_sessions")
    op.drop_table("owner_auth_states")
    op.drop_table("owner_auth_identity")
