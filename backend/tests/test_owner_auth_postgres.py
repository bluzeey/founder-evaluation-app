"""Real PostgreSQL migration check on an explicitly named, empty local test DB."""
import hashlib
import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pathlib import Path


@pytest.fixture(autouse=True)
def clean_tables():
    # This module owns its separate migration DB, never the business-test DB.
    yield


def test_postgres_owner_migration_preserves_business_data(monkeypatch):
    url = os.environ.get("FOUNDEROS_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set an empty private local migration-test database")
    parsed = sa.engine.make_url(url)
    assert parsed.database == "founder_test"
    assert parsed.host is None and str(parsed.query.get("host", "")).startswith("/private/tmp/founder-pg-test-")
    engine = sa.create_engine(url)
    assert sa.inspect(engine).get_table_names() == [], "Migration DB must be empty and disposable"
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    monkeypatch.setenv("DATABASE_URL", url)

    def business_signature():
        with engine.connect() as connection:
            names = connection.exec_driver_sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name").scalars().all()
            out = {}
            for name in names:
                if name == "alembic_version" or name.startswith("owner_auth_"):
                    continue
                quoted = '"' + name.replace('"', '""') + '"'
                rows = connection.exec_driver_sql("SELECT row_to_json(t)::text FROM " + quoted + " t ORDER BY row_to_json(t)::text").scalars().all()
                out[name] = (len(rows), hashlib.sha256("\n".join(rows).encode()).hexdigest())
            return out

    try:
        command.upgrade(config, "d1e2f3a4b5c6")
        import db_models
        from database import Base
        from owner_auth import AUTH_METADATA, owner, oauth_states
        with sa.orm.Session(engine) as session:
            session.add(db_models.Founder(id="migration-fixture", name="Synthetic migration fixture", email="fixture@example.test", enrichment_policy="MANUAL"))
            session.add(db_models.Thesis(id="migration-thesis", name="Synthetic migration thesis"))
            session.commit()
        before = business_signature()
        # Historical migrations seed demo rows; preserve those as well as our
        # two fixtures rather than assuming the baseline is otherwise empty.
        assert sum(count for count, _ in before.values()) >= 2
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM founders WHERE id='migration-fixture'").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT count(*) FROM theses WHERE id='migration-thesis'").scalar_one() == 1
        command.upgrade(config, "head")
        assert business_signature() == before
        with engine.begin() as connection:
            connection.execute(oauth_states.insert().values(state_hash="s" * 64, browser_hash="b" * 64, nonce="n" * 43, pkce_verifier="v" * 43, expires_at=1_999_999_999))
            first = connection.execute(oauth_states.delete().where(oauth_states.c.state_hash == "s" * 64).returning(oauth_states)).mappings().first()
            assert first is not None
            assert connection.execute(oauth_states.delete().where(oauth_states.c.state_hash == "s" * 64).returning(oauth_states)).first() is None
            context = MigrationContext.configure(connection)
            changes = compare_metadata(context, [Base.metadata, AUTH_METADATA])
            assert not any(change[0] == "remove_table" and change[1].name.startswith("owner_auth_") for change in changes if isinstance(change, tuple))
        command.downgrade(config, "d1e2f3a4b5c6")
        assert business_signature() == before
        assert not any(name.startswith("owner_auth_") for name in sa.inspect(engine).get_table_names())
        command.upgrade(config, "head")
        assert business_signature() == before
    finally:
        # The guarded local DB contains only this test's fixtures and historical
        # demo seeds. Avoid unrelated historical downgrade implementations.
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
        engine.dispose()
