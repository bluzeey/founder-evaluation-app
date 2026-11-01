"""Allow independent Google identities without assigning any business data.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2

Email is deliberately non-unique: Google subjects are immutable, emails can
change/recur. Never merge principals or assign legacy records using email.
The existing integer primary key already allocates IDs (SERIAL on PostgreSQL).
SQLite callers must disable foreign keys outside the migration transaction for
Alembic batch recreation; otherwise this revision refuses to run. PostgreSQL
uses ALTER and keeps foreign keys enforced.
Downgrade refuses incompatible identities rather than deleting/rebinding them.
"""
from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None

_SQLITE_NAMES = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _require_sqlite_batch_safety():
    # Dropping/recreating a referenced table with PRAGMA foreign_keys=ON could
    # cascade-delete sessions. Never toggle this pragma inside a transaction.
    if op.get_bind().exec_driver_sql("PRAGMA foreign_keys").scalar():
        raise RuntimeError("SQLite auth migration requires foreign_keys=OFF before its transaction")


def upgrade():
    if op.get_context().dialect.name == "sqlite":
        _require_sqlite_batch_safety()
        with op.batch_alter_table("owner_auth_identity", naming_convention=_SQLITE_NAMES) as batch:
            batch.drop_constraint("ck_owner_auth_single_owner", type_="check")
            batch.drop_constraint("uq_owner_auth_identity_email", type_="unique")
    else:
        op.drop_constraint("ck_owner_auth_single_owner", "owner_auth_identity", type_="check")
        op.drop_constraint("owner_auth_identity_email_key", "owner_auth_identity", type_="unique")
        # The former singleton was inserted with id=1 explicitly, which never
        # advanced SERIAL. Keep its principal/session, reserve no default owner,
        # and let the next insert allocate a free ID even on populated installs.
        # Do not rewind an already advanced sequence. ALTER holds the table lock
        # until commit; no concurrent identity INSERT can race this adjustment.
        op.execute(sa.text("""
            SELECT setval(
                pg_get_serial_sequence('owner_auth_identity', 'id'),
                GREATEST(
                    COALESCE((SELECT MAX(id) FROM owner_auth_identity), 0) + 1,
                    nextval(pg_get_serial_sequence('owner_auth_identity', 'id'))
                ),
                false
            )
        """))


def downgrade():
    if not op.get_context().as_sql:
        identity = sa.table("owner_auth_identity", sa.column("id"))
        if op.get_bind().execute(sa.select(identity.c.id).where(identity.c.id != 1).limit(1)).first():
            raise RuntimeError("Cannot restore singleton auth while multiple/non-owner identities exist")
    if op.get_context().dialect.name == "sqlite":
        _require_sqlite_batch_safety()
        with op.batch_alter_table("owner_auth_identity") as batch:
            batch.create_check_constraint("ck_owner_auth_single_owner", "id = 1")
            batch.create_unique_constraint("uq_owner_auth_identity_email", ["email"])
    else:
        op.create_check_constraint("ck_owner_auth_single_owner", "owner_auth_identity", "id = 1")
        op.create_unique_constraint("owner_auth_identity_email_key", "owner_auth_identity", ["email"])
