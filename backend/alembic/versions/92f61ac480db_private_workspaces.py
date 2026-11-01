"""Add private workspace registry without changing existing business records.

Revision ID: 92f61ac480db
Revises: f8a9b0c1d2e3
"""
from alembic import op
import sqlalchemy as sa

revision = "92f61ac480db"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "owner_auth_workspaces",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("owner_auth_identity.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("schema_name", sa.String(63), nullable=False, unique=True),
        sa.Column("schema_revision", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("legacy_copied", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("uq_founderos_legacy_workspace", "owner_auth_workspaces", ["legacy_copied"], unique=True,
                    postgresql_where=sa.text("legacy_copied IS TRUE"), sqlite_where=sa.text("legacy_copied IS 1"))
    if op.get_context().dialect.name == "postgresql":
        # Business roles never receive the held legacy data or auth controls via
        # PostgreSQL's implicit PUBLIC role. Admin ownership stays unchanged.
        names = ("founders", "theses", "evidence_items", "score_snapshots",
                 "social_media_backgrounds", "founder_csv_imports", "founder_screening_profiles",
                 "founder_pool_items", "opportunities", "claims", "sourcing_schedules",
                 "sourcing_jobs", "enrichment_runs", "owner_auth_identity",
                 "owner_auth_states", "owner_auth_sessions", "owner_auth_workspaces")
        for name in names:
            op.execute(sa.text('REVOKE ALL ON TABLE public."' + name + '" FROM PUBLIC'))


def downgrade():
    if not op.get_context().as_sql:
        count = op.get_bind().execute(sa.text("SELECT count(*) FROM owner_auth_workspaces")).scalar_one()
        if count:
            raise RuntimeError("Cannot remove the private workspace registry while workspaces exist")
    op.drop_index("uq_founderos_legacy_workspace", table_name="owner_auth_workspaces")
    op.drop_table("owner_auth_workspaces")
