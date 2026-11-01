import os
import sys
from functools import lru_cache
from pathlib import Path

# Use the test database for all tests. Must be set before any backend module is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "FOUNDEROS_TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:founderos@localhost:5433/founderos_test",
)
os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient

_test_url = make_url(os.environ["DATABASE_URL"])
assert _test_url.database in {"founderos_test", "founder_test"}, "Use a disposable FounderOS test database"
assert _test_url.host in {None, "localhost", "127.0.0.1", "::1"}, "Tests must never connect to a remote database"
if _test_url.query.get("host"):
    assert str(_test_url.query["host"]).startswith("/private/tmp/founder-pg-test-"), "Use the private test socket"


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Provider traffic is forbidden; PostgreSQL uses its local native driver."""
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError("External network calls are forbidden in backend tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@lru_cache(maxsize=1)
def _business_runtime():
    """Keep auth unit-test collection entirely separate from PostgreSQL/main."""
    from database import Base, SessionLocal, engine, get_db
    from main import app
    from owner_auth import AUTH_METADATA

    # All schemas in this guarded database are disposable test fixtures.
    with engine.begin() as connection:
        names = connection.execute(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'founderos_user_%'")).scalars().all()
        for name in names:
            assert name.removeprefix("founderos_user_").isdigit()
            connection.exec_driver_sql('DROP SCHEMA "' + name + '" CASCADE')
        from private_workspaces import role_for_user
        role_prefix = role_for_user(connection, 1).rsplit("_", 1)[0] + "_"
        roles = connection.execute(text("SELECT rolname FROM pg_roles WHERE rolname LIKE :prefix"), {"prefix": role_prefix + "%"}).scalars().all()
        for name in roles:
            assert name.removeprefix(role_prefix).isdigit()
            connection.exec_driver_sql('DROP OWNED BY "' + name + '"')
            connection.exec_driver_sql('DROP ROLE "' + name + '"')
    AUTH_METADATA.drop_all(bind=engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    AUTH_METADATA.create_all(bind=engine)
    import owner_auth as auth
    from private_workspaces import provision_workspace
    with engine.begin() as connection:
        connection.execute(auth.owner.insert().values(id=1, email="owner@example.test", google_sub="pytest-owner", created_at=auth._now()))
    provision_workspace(1)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, SessionLocal


@pytest.fixture
def db():
    """Provide a fresh DB session for a test."""
    _, SessionLocal = _business_runtime()
    from workspace_context import user_scope
    with user_scope(1):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


@pytest.fixture
def owner_session(monkeypatch):
    """Explicit synthetic DB session; exercises the production guard without OAuth.

    This fixture lives only in pytest. Production has no auth bypass or test flag.
    """
    import secrets
    import owner_auth as auth

    _, SessionLocal = _business_runtime()
    for name, value in {
        "GOOGLE_CLIENT_ID": "pytest-client", "GOOGLE_CLIENT_SECRET": "pytest-secret",
        "REDIRECT_URI": "https://founder-os-dev.vercel.app/api/auth/google/callback",
        "FRONTEND_ORIGIN": "https://founder-os-dev.vercel.app",
        "WORKSPACE_MODE": "private",
    }.items():
        monkeypatch.setenv("FOUNDEROS_" + name, value)
    raw, now = secrets.token_urlsafe(32), auth._now()
    from database import engine
    with engine.begin() as connection:
        connection.execute(auth.sessions.delete())
        connection.execute(auth.oauth_states.delete())
        connection.execute(auth.sessions.insert().values(
            session_hash=auth._hash(raw), owner_id=1, created_at=now,
            expires_at=now + auth.SESSION_TTL,
        ))
    return raw


@pytest.fixture
def client(owner_session):
    """Business API tests use a real, synthetic owner session and exact Origin."""
    import owner_auth as auth

    app, _ = _business_runtime()
    with TestClient(app, base_url="https://founder-os-dev.vercel.app",
                    headers={"Origin": "https://founder-os-dev.vercel.app"}) as test_client:
        test_client.cookies.set(auth.SESSION_COOKIE, owner_session,
                                domain="founder-os-dev.vercel.app", path="/")
        yield test_client


@pytest.fixture(autouse=True)
def clean_tables(request):
    """Truncate all tables after each test to keep tests isolated."""
    yield
    if request.node.path.name == "test_owner_auth.py":
        return
    _, SessionLocal = _business_runtime()
    from workspace_context import user_scope
    with user_scope(1):
        db = SessionLocal()
        try:
            db.execute(
                text(
                    "TRUNCATE founder_screening_profiles, founder_csv_imports, claims, opportunities, score_snapshots, evidence_items, "
                    "social_media_backgrounds, founder_pool_items, theses, founders CASCADE"
                )
            )
            db.commit()
        finally:
            db.close()
