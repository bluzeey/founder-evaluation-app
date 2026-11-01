"""Private PostgreSQL schemas selected only by verified immutable user IDs.

New workspaces start empty. Existing public tables remain a held recovery copy;
only the explicit operator helper can copy them to a verified legacy owner.
The app never uses public as a fallback for business queries.
"""
import hashlib
import time
from contextlib import contextmanager

import sqlalchemy as sa

from owner_auth import _Unavailable, owner, workspaces
from workspace_context import user_scope, validate_user_id

SCHEMA_REVISION = "business-d1e2f3a4b5c6-v1"
BUSINESS_TABLES = frozenset({
    "founders", "theses", "evidence_items", "score_snapshots",
    "social_media_backgrounds", "founder_csv_imports", "founder_screening_profiles",
    "founder_pool_items", "opportunities", "claims", "sourcing_schedules",
    "sourcing_jobs", "enrichment_runs",
})
_LOCK_NAMESPACE = 1146242387


def schema_for_user(user_id):
    return "founderos_user_" + str(validate_user_id(user_id))


def role_for_user(connection, user_id):
    # PostgreSQL roles span the whole cluster. Keep identical user IDs in other
    # databases (including restore/test databases) on distinct restricted roles.
    database = connection.engine.url.database
    if not database:
        raise _Unavailable()
    namespace = hashlib.sha256(database.encode()).hexdigest()[:12]
    return "founderos_role_" + namespace + "_" + str(validate_user_id(user_id))


def _metadata(schema):
    from database import Base
    import db_models  # noqa: F401
    if set(Base.metadata.tables) != BUSINESS_TABLES:
        raise _Unavailable()
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata, schema=schema)
    return metadata


def _create_workspace_role(connection, schema, user_id):
    quote = connection.dialect.identifier_preparer.quote
    role = quote(role_for_user(connection, user_id))
    quoted_schema = quote(schema)
    connection.exec_driver_sql("CREATE ROLE " + role + " NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS")
    connection.exec_driver_sql("REVOKE ALL ON SCHEMA " + quoted_schema + " FROM PUBLIC")
    connection.exec_driver_sql("GRANT USAGE ON SCHEMA " + quoted_schema + " TO " + role)
    connection.exec_driver_sql("GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA " + quoted_schema + " TO " + role)
    connection.exec_driver_sql("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA " + quoted_schema + " TO " + role)


def workspace_schema(connection, user_id):
    """Resolve only an existing, versioned registry entry; never public."""
    expected = schema_for_user(user_id)
    row = connection.execute(sa.text(
        "SELECT schema_name, schema_revision FROM public.owner_auth_workspaces WHERE user_id=:user_id"
    ), {"user_id": user_id}).mappings().first()
    if row is None or row["schema_name"] != expected or row["schema_revision"] != SCHEMA_REVISION:
        raise _Unavailable()
    exists = connection.execute(sa.text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": expected}).scalar_one()
    if not exists:
        raise _Unavailable()
    role = connection.execute(sa.text(
        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname=:schema"
    ), {"schema": role_for_user(connection, user_id)}).first()
    if role is None or any(role):
        raise _Unavailable()
    return expected


def _provision(connection, user_id):
    schema = schema_for_user(user_id)
    if connection.dialect.name != "postgresql":
        raise _Unavailable()
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(:namespace, :user_id)"),
                       {"namespace": _LOCK_NAMESPACE, "user_id": user_id})
    if connection.execute(sa.select(owner.c.id).where(owner.c.id == user_id)).scalar_one_or_none() is None:
        raise _Unavailable()
    row = connection.execute(sa.select(workspaces).where(workspaces.c.user_id == user_id)).mappings().first()
    if row:
        # pg_dump restores database schemas/registry but not cluster-wide roles.
        # Recreate only the exact role named by this validated registry entry.
        if row["schema_name"] != schema or row["schema_revision"] != SCHEMA_REVISION:
            raise _Unavailable()
        if not connection.execute(sa.text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": schema}).scalar_one():
            raise _Unavailable()
        if not connection.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:schema"), {"schema": role_for_user(connection, user_id)}).first():
            _create_workspace_role(connection, schema, user_id)
        return workspace_schema(connection, user_id)
    # An orphaned schema is never adopted or exposed to a new principal.
    if connection.execute(sa.text("SELECT to_regnamespace(:schema)"), {"schema": schema}).scalar_one() is not None:
        raise _Unavailable()
    if connection.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:schema"), {"schema": role_for_user(connection, user_id)}).first():
        raise _Unavailable()
    connection.execute(sa.schema.CreateSchema(schema))
    _metadata(schema).create_all(connection)
    _create_workspace_role(connection, schema, user_id)
    connection.execute(workspaces.insert().values(
        user_id=user_id, schema_name=schema, schema_revision=SCHEMA_REVISION,
        created_at=int(time.time()), legacy_copied=False,
    ))
    return schema


def provision_workspace(user_id):
    from database import engine
    with engine.begin() as connection:
        return _provision(connection, validate_user_id(user_id))


@contextmanager
def private_data_scope(user_id):
    # Provisioning is transactional and serialized for simultaneous first loads.
    provision_workspace(user_id)
    with user_scope(user_id):
        yield


def _signature(connection, schema):
    quote = connection.dialect.identifier_preparer.quote
    result = {}
    for name in sorted(BUSINESS_TABLES):
        rows = connection.exec_driver_sql(
            "SELECT to_jsonb(t)::text FROM " + quote(schema) + "." + quote(name) +
            " t ORDER BY to_jsonb(t)::text"
        ).scalars().all()
        result[name] = (len(rows), hashlib.sha256("\n".join(rows).encode()).hexdigest())
    return result


def copy_legacy_to_verified_owner(google_sub, email):
    """Operator-only helper; never an HTTP endpoint or a first-signup rule.

    Call after source writes stop and the final source copy is verified. Supply
    the owner's independently verified Google subject privately. This operation
    creates/preserves that exact principal, copies into its empty workspace, and
    verifies every row. A second legacy owner or non-empty destination refuses.
    Original tables stay intact. No tokens or credentials are accepted here.
    """
    from database import engine
    if (not isinstance(google_sub, str) or not google_sub or len(google_sub) > 255
            or not isinstance(email, str) or "@" not in email or len(email) > 320):
        raise _Unavailable()
    with engine.begin() as connection:
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(:namespace, 0)"), {"namespace": _LOCK_NAMESPACE})
        identity = connection.execute(sa.select(owner).where(owner.c.google_sub == google_sub)).mappings().first()
        if identity is None:
            user_id = connection.execute(owner.insert().values(
                google_sub=google_sub, email=email.casefold(), created_at=int(time.time()),
            ).returning(owner.c.id)).scalar_one()
        else:
            user_id = identity["id"]
        schema = _provision(connection, user_id)
        registry = connection.execute(sa.select(workspaces).where(workspaces.c.user_id == user_id)).mappings().one()
        if registry["legacy_copied"]:
            raise _Unavailable()  # Never replay an old snapshot over live edits.
        if connection.execute(sa.select(workspaces.c.user_id).where(workspaces.c.legacy_copied.is_(True))).first():
            raise _Unavailable()
        if any(count for count, digest in _signature(connection, schema).values()):
            raise _Unavailable()
        before = _signature(connection, "public")
        quote = connection.dialect.identifier_preparer.quote
        for table in _metadata(schema).sorted_tables:
            columns = ", ".join(quote(column.name) for column in table.columns)
            connection.exec_driver_sql(
                "INSERT INTO " + quote(schema) + "." + quote(table.name) + " (" + columns + ") "
                "SELECT " + columns + " FROM public." + quote(table.name)
            )
        if _signature(connection, schema) != before or _signature(connection, "public") != before:
            raise _Unavailable()
        connection.execute(workspaces.update().where(workspaces.c.user_id == user_id).values(legacy_copied=True))
        return {"user_id": user_id, "tables_preserved": len(before),
                "rows_preserved": sum(count for count, digest in before.values())}
