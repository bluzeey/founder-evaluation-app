"""Real local PostgreSQL isolation; run serially with the business test suite.

Only synthetic identities/data are created. OAuth, providers and queues are
never used. The optional legacy-copy check requires its own empty migration DB.
"""
import csv
import hashlib
import io
import os
import secrets
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import _business_runtime


ORIGIN = "https://founder-os-dev.vercel.app"
TABLES = frozenset({
    "founders", "theses", "evidence_items", "score_snapshots",
    "social_media_backgrounds", "founder_csv_imports", "founder_screening_profiles",
    "founder_pool_items", "opportunities", "claims", "sourcing_schedules",
    "sourcing_jobs", "enrichment_runs",
})


def _json(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


@contextmanager
def _session(accounts, account):
    from workspace_context import user_scope
    with user_scope(account.id), accounts.SessionLocal() as session:
        yield session


def _snapshot(engine, schema):
    """Independent row comparison, including JSON, FK values and timestamps."""
    with engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        return {name: tuple(connection.exec_driver_sql(
            "SELECT to_jsonb(t)::text FROM " + quote(schema) + "." + quote(name)
            + " t ORDER BY to_jsonb(t)::text"
        ).scalars()) for name in sorted(TABLES)}


@pytest.fixture
def accounts(monkeypatch):
    import owner_auth as auth
    import private_workspaces as private
    from database import engine

    for name, value in {
        "GOOGLE_CLIENT_ID": "pytest-private-client",
        "GOOGLE_CLIENT_SECRET": "pytest-private-secret",
        "REDIRECT_URI": ORIGIN + "/api/auth/google/callback",
        "FRONTEND_ORIGIN": ORIGIN, "WORKSPACE_MODE": "private",
    }.items():
        monkeypatch.setenv("FOUNDEROS_" + name, value)
    app, factory = _business_runtime()
    assert engine.dialect.name == "postgresql"

    def forbidden(*args, **kwargs):
        raise AssertionError("Private workspace tests must not call providers or queues")

    # Fail immediately if an ordinary save accidentally starts background work.
    import ai_policy
    import main
    import research
    from celery.app.task import Task
    monkeypatch.setattr(Task, "apply_async", forbidden)
    monkeypatch.setattr(ai_policy, "_store", forbidden)
    monkeypatch.setattr(main, "queue_manual_task", forbidden)
    for name in ("OpenAIClient", "SocialAgent", "SourcingAgent", "DocumentAgent"):
        monkeypatch.setattr(getattr(research, name), "__init__", forbidden)

    nonce, now = secrets.token_hex(8), auth._now()
    people = []
    with engine.begin() as connection:
        # The conftest owner uses an explicit id=1; avoid its sequence entirely.
        first = max(1001, connection.execute(sa.select(sa.func.max(auth.owner.c.id))).scalar_one() + 1)
        for index in range(2):
            person = SimpleNamespace(id=first + index, sub=f"pytest-private-{nonce}-{index}",
                                     email="same-address@example.test", raw=secrets.token_urlsafe(32))
            person.schema = private.schema_for_user(person.id)
            person.role = private.role_for_user(connection, person.id)
            connection.execute(auth.owner.insert().values(
                id=person.id, google_sub=person.sub, email=person.email, created_at=now))
            connection.execute(auth.sessions.insert().values(
                session_hash=auth._hash(person.raw), owner_id=person.id,
                created_at=now, expires_at=now + auth.SESSION_TTL))
            people.append(person)
    try:
        with ExitStack() as stack:
            for person in people:
                person.client = stack.enter_context(TestClient(
                    app, base_url=ORIGIN, headers={"Origin": ORIGIN}))
                person.client.cookies.set(auth.SESSION_COOKIE, person.raw,
                                          domain="founder-os-dev.vercel.app", path="/")
            yield SimpleNamespace(left=people[0], right=people[1], people=people,
                                  engine=engine, SessionLocal=factory, app=app)
    finally:
        # Remove only this fixture's two schemas/roles/identities, never baseline data.
        with engine.begin() as connection:
            quote = connection.dialect.identifier_preparer.quote
            for person in people:
                connection.exec_driver_sql("DROP SCHEMA IF EXISTS " + quote(person.schema) + " CASCADE")
                if connection.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"),
                                      {"role": person.role}).first():
                    connection.exec_driver_sql("DROP OWNED BY " + quote(person.role))
                    connection.exec_driver_sql("DROP ROLE " + quote(person.role))
                connection.execute(auth.workspaces.delete().where(auth.workspaces.c.user_id == person.id))
                connection.execute(auth.owner.delete().where(auth.owner.c.id == person.id))


def _create_case(person, marker):
    client = person.client
    founder = _json(client.post("/v1/founders", json={
        "name": marker, "email": marker + "@example.test", "enrichment_policy": "MANUAL"}))
    thesis = _json(client.post("/v1/theses", json={"name": marker + " thesis"}))
    profile = _json(client.put(f"/v1/founders/{founder['id']}/screening-profile", json={
        "project_name": marker, "city": marker + " city", "sector": marker + " sector",
        "founder_score": 85, "founder_score_rationale": marker,
        "vision_product_score": 40, "differentiation_score": 40, "traction_score": 30}))
    opportunity = marker + "-opportunity"
    _json(client.post(f"/v1/opportunities/{opportunity}/screen", params={"founder_id": founder["id"]}))
    schedule = _json(client.post("/v1/sourcing/schedules", json={"thesis_id": thesis["id"]}))
    _json(client.post(f"/v1/opportunities/{opportunity}/deck", params={"founder_id": founder["id"]},
                      files={"file": ("synthetic.txt", marker.encode(), "text/plain")}))
    return SimpleNamespace(founder=founder["id"], thesis=thesis["id"], profile=profile["id"],
                           opportunity=opportunity, schedule=schedule["id"], marker=marker)


def _evidence(founder, marker):
    return {"id": marker, "founder_id": founder, "dimension": "execution_and_shipping",
            "observation": marker, "source_type": "test", "source_id": marker,
            "source_locator": "synthetic fixture", "evidence_type": "inspected_artifact",
            "rubric_level": 3, "source_trust": 0.8, "task_relevance": 0.8,
            "recency_factor": 1.0, "independence_group": marker,
            "polarity": "positive", "status": "positive"}


def _seed_all_tables(session, marker):
    """One real row per business table, with real cross-table relationships."""
    import db_models as m
    ids = {name: marker + "-" + name for name in TABLES}
    session.add(m.Founder(id=ids["founders"], name=marker, email=marker + "@example.test",
                          enrichment_policy="MANUAL"))
    session.add(m.Thesis(id=ids["theses"], name=marker))
    session.add(m.FounderCsvImport(id=ids["founder_csv_imports"], file_name="synthetic.csv",
                                  file_checksum=hashlib.sha256(marker.encode()).hexdigest(), row_count=1))
    session.flush()
    session.add(m.Opportunity(id=ids["opportunities"], founder_id=ids["founders"]))
    session.add(m.SourcingSchedule(id=ids["sourcing_schedules"], thesis_id=ids["theses"], enabled=False))
    session.flush()
    session.add_all([
        m.EvidenceItem(**_evidence(ids["founders"], ids["evidence_items"])),
        m.ScoreSnapshot(id=ids["score_snapshots"], founder_id=ids["founders"],
                        rubric_version="synthetic", prompt_version="synthetic", model_version="synthetic",
                        founder_score=50, evidence_band_low=0, evidence_band_high=100,
                        overall_confidence=0, evidence_coverage=0),
        m.SocialMediaBackground(id=ids["social_media_backgrounds"], founder_id=ids["founders"]),
        m.FounderScreeningProfile(id=ids["founder_screening_profiles"], founder_id=ids["founders"],
                                 external_record_id="same-external-record", import_id=ids["founder_csv_imports"]),
        m.FounderPoolItem(id=ids["founder_pool_items"], name=marker, reason=marker,
                          thesis_id=ids["theses"], job_id=ids["sourcing_jobs"]),
        m.Claim(id=ids["claims"], founder_id=ids["founders"], opportunity_id=ids["opportunities"],
                claim=marker, source="synthetic.txt", trust_status="founder_reported", confidence=0),
        m.SourcingJob(id=ids["sourcing_jobs"], thesis_id=ids["theses"],
                      schedule_id=ids["sourcing_schedules"], status="running"),
        m.EnrichmentRun(id=ids["enrichment_runs"], founder_id=ids["founders"], stage="social"),
    ])
    session.commit()
    return ids


def test_same_email_distinct_subjects_get_empty_versioned_workspaces(accounts):
    import owner_auth as auth
    from private_workspaces import BUSINESS_TABLES, SCHEMA_REVISION, provision_workspace
    assert BUSINESS_TABLES == TABLES
    assert accounts.left.sub != accounts.right.sub
    for person in accounts.people:
        principal = _json(person.client.get("/auth/me"))
        assert principal["user_id"] == person.id
        assert principal["email"] == person.email
        assert principal["workspace_mode"] == "private"
        _json(person.client.get("/v1/founders")) == []
        assert not any(_snapshot(accounts.engine, person.schema).values())
        assert provision_workspace(person.id) == person.schema
        with accounts.engine.connect() as connection:
            row = connection.execute(sa.select(auth.workspaces).where(
                auth.workspaces.c.user_id == person.id)).mappings().one()
            assert row["schema_name"] == person.schema
            assert row["schema_revision"] == SCHEMA_REVISION
            assert row["legacy_copied"] is False
            stored = connection.execute(sa.select(auth.sessions.c.session_hash).where(
                auth.sessions.c.owner_id == person.id)).scalar_one()
            assert stored == auth._hash(person.raw) and stored != person.raw


@pytest.mark.parametrize("victim_index", [0, 1])
def test_other_accounts_ids_cannot_be_read_or_changed(accounts, victim_index):
    victim, attacker = accounts.people[victim_index], accounts.people[1 - victim_index]
    case = _create_case(victim, "secret-" + str(victim_index))
    _json(attacker.client.get("/v1/founders"))
    before = _snapshot(accounts.engine, victim.schema)
    for path in (f"/v1/founders/{case.founder}", f"/v1/founders/{case.founder}/screening-profile",
                 f"/v1/founders/{case.founder}/social-background", f"/v1/founders/{case.founder}/score",
                 f"/v1/founders/{case.founder}/history", f"/v1/theses/{case.thesis}",
                 f"/v1/opportunities/{case.opportunity}", f"/v1/sourcing/schedules/{case.schedule}"):
        _json(attacker.client.get(path), 404)
    for method, path, body in (
        ("put", f"/v1/founders/{case.founder}/screening-profile", {"project_name": "stolen"}),
        ("post", f"/v1/founders/{case.founder}/evidence", {"items": [_evidence(case.founder, "attack")]}),
        ("put", f"/v1/theses/{case.thesis}", {"name": "stolen"}),
        ("patch", f"/v1/opportunities/{case.opportunity}/status", {"status": "INVESTED"}),
        ("put", f"/v1/sourcing/schedules/{case.schedule}", {"interval_seconds": 999}),
        ("post", "/v1/sourcing/schedules", {"thesis_id": case.thesis}),
    ):
        _json(getattr(attacker.client, method)(path, json=body), 404)
    _json(attacker.client.delete(f"/v1/sourcing/schedules/{case.schedule}"), 404)
    _json(attacker.client.post(f"/v1/opportunities/{case.opportunity}/screen",
                              params={"founder_id": case.founder}), 404)
    _json(attacker.client.post(f"/v1/opportunities/{case.opportunity}/deck",
                              files={"file": ("attack.txt", b"stolen", "text/plain")}), 404)
    assert _json(attacker.client.get(f"/v1/opportunities/{case.opportunity}/diligence")) == []
    assert _snapshot(accounts.engine, victim.schema) == before
    assert not any(_snapshot(accounts.engine, attacker.schema).values())


def test_lists_search_facets_and_counts_do_not_leak(accounts):
    from private_workspaces import provision_workspace
    left, right = accounts.people
    provision_workspace(left.id)
    with _session(accounts, left) as session:
        ids = _seed_all_tables(session, "private-search-sentinel")
    for path in ("/v1/founders", "/v1/theses", "/v1/opportunities", "/v1/founders/pool",
                 "/v1/sourcing/schedules", "/v1/sourcing/jobs", "/v1/enrichment/runs",
                 "/v1/opportunities?founder_id=" + ids["founders"],
                 "/v1/sourcing/jobs?thesis_id=" + ids["theses"],
                 "/v1/founders/pool?job_id=" + ids["sourcing_jobs"],
                 "/v1/enrichment/runs?founder_id=" + ids["founders"]):
        assert _json(right.client.get(path)) == []
    for path in ("/v1/founders/discovery", "/v1/founders/recommended"):
        for params in ({"include_unscreened": "true"}, {"q": "private-search-sentinel"}):
            page = _json(right.client.get(path, params=params))
            assert page["total"] == 0 and page["items"] == []
            assert all(value == [] for value in page["facets"].values())
    status = _json(right.client.get("/v1/sourcing/status"))
    assert status["schedules"] == status["active_jobs"] == status["recent_jobs"] == []
    status = _json(right.client.get("/v1/enrichment/status"))
    assert status["below_threshold_count"] == 0 and status["recent_runs"] == []
    assert len(_json(left.client.get("/v1/founders"))) == 1


def test_same_client_ids_and_csv_external_ids_are_independent(accounts):
    # Opportunity and evidence IDs are supplied by the caller; neither is global.
    for index, person in enumerate(accounts.people):
        case = _create_case(person, "account-" + str(index))
        _json(person.client.post("/v1/opportunities/shared-client-id/screen",
                                  params={"founder_id": case.founder}))
        _json(person.client.post(f"/v1/founders/{case.founder}/evidence", json={
            "items": [_evidence(case.founder, "shared-evidence-id")]}))
        assert _json(person.client.get("/v1/opportunities/shared-client-id"))["founder_id"] == case.founder

    row = {"record_id": "shared-csv-record", "founder_name": "Same CSV Founder",
           "project_name": "Same CSV Project", "primary_source_url": "https://example.test/synthetic",
           "funding_status": "unknown", "founder_score": 80, "founder_score_rationale": "Synthetic",
           "vision_product_score": 40, "vision_product_rationale": "Synthetic",
           "differentiation_score": 40, "differentiation_rationale": "Synthetic",
           "traction_score": 30, "traction_rationale": "Synthetic", "evaluation_version": "associate_screen_v1"}
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    payload = stream.getvalue().encode()
    imported = []
    for person in accounts.people:
        result = _json(person.client.post("/v1/founders/import-csv?dry_run=false",
                                          files={"file": ("same.csv", payload, "text/csv")}))
        assert result["errors"] == [] and result["founders_to_create"] == 1
        assert result["profiles_to_create"] == 1 and result["founders_to_update"] == 0
        imported.append(result["created_founder_ids"][0])
        _json(person.client.post("/v1/founders/import-csv?dry_run=false",
                                files={"file": ("same.csv", payload, "text/csv")}), 409)
    for index, person in enumerate(accounts.people):
        _json(person.client.get("/v1/founders/" + imported[1 - index]), 404)
    before = _snapshot(accounts.engine, accounts.left.schema)
    _json(accounts.right.client.post("/v1/founders/import-csv?dry_run=false&force=true",
                                    files={"file": ("same.csv", payload, "text/csv")}))
    assert _snapshot(accounts.engine, accounts.left.schema) == before


def test_all_13_tables_orm_and_literal_sql_share_only_current_schema(accounts):
    from database import Base
    from private_workspaces import provision_workspace
    assert set(Base.metadata.tables) == TABLES
    for person in accounts.people:
        provision_workspace(person.id)
        with _session(accounts, person) as session:
            _seed_all_tables(session, "same-ids")
            session.execute(sa.text("UPDATE founders SET name=:name"), {"name": person.sub})
            session.commit()
    for person in (accounts.left, accounts.right, accounts.left):
        with _session(accounts, person) as session:
            for table in TABLES:
                assert session.execute(sa.select(Base.metadata.tables[table].c.id)).scalars().all() == ["same-ids-" + table]
                assert session.execute(sa.text('SELECT id FROM "' + table + '"')).scalars().all() == ["same-ids-" + table]
            assert session.execute(sa.text("SELECT name FROM founders")).scalar_one() == person.sub
            assert session.execute(sa.text("SELECT current_user")).scalar_one() == person.role
            assert "public" not in session.execute(sa.text("SELECT current_schemas(false)")).scalar_one()


@pytest.mark.parametrize("target", ["public", "other"])
@pytest.mark.parametrize("statement", ["SELECT * FROM {schema}.founders", "UPDATE {schema}.founders SET name='attack'",
                                       "DELETE FROM {schema}.founders", "TRUNCATE {schema}.founders CASCADE"])
def test_explicit_public_and_other_schema_sql_permission_denied(accounts, target, statement):
    from private_workspaces import provision_workspace
    for person in accounts.people:
        provision_workspace(person.id)
    schema = "public" if target == "public" else accounts.right.schema
    before = _snapshot(accounts.engine, schema)
    with _session(accounts, accounts.left) as session:
        with pytest.raises(sa.exc.DBAPIError) as error:
            session.execute(sa.text(statement.format(schema='"' + schema + '"')))
        assert error.value.orig.pgcode == "42501"
        session.rollback()
        assert session.execute(sa.text("SELECT current_user")).scalar_one() == accounts.left.role
    assert _snapshot(accounts.engine, schema) == before


def test_pool_reuse_commit_rollback_savepoint_and_scoped_truncate(accounts):
    from database import WorkspaceSession
    from private_workspaces import provision_workspace
    from workspace_context import user_scope
    for person in accounts.people:
        provision_workspace(person.id)
        with _session(accounts, person) as session:
            _seed_all_tables(session, person.sub)
    before = _snapshot(accounts.engine, accounts.right.schema)
    # One checked-out physical connection proves role/path reset and reuse.
    with accounts.engine.connect() as connection:
        original = connection.exec_driver_sql("SELECT current_user, current_setting('search_path'), pg_backend_pid()").one()
        connection.rollback()
        for person in (accounts.left, accounts.right, accounts.left):
            with user_scope(person.id), WorkspaceSession(bind=connection) as session:
                assert session.execute(sa.text("SELECT pg_backend_pid()")).scalar_one() == original[2]
                assert session.execute(sa.text("SELECT name FROM founders")).scalar_one() == person.sub
                with session.begin_nested():
                    session.execute(sa.text("UPDATE founders SET name='rolled-back'"))
                session.rollback()
                assert session.execute(sa.text("SELECT name FROM founders")).scalar_one() == person.sub
                session.commit()
            restored = connection.exec_driver_sql("SELECT current_user, current_setting('search_path')").one()
            assert tuple(restored) == tuple(original[:2])
            connection.rollback()
    with _session(accounts, accounts.left) as session:
        session.execute(sa.text("TRUNCATE " + ", ".join(sorted(TABLES)) + " CASCADE"))
        session.commit()
    assert not any(_snapshot(accounts.engine, accounts.left.schema).values())
    assert _snapshot(accounts.engine, accounts.right.schema) == before


@pytest.mark.parametrize("operation", ["get", "query_get", "execute", "scalar", "scalars", "query", "flush", "connection"])
def test_reused_session_cannot_cross_identity_even_with_cached_founder(accounts, operation):
    import db_models as m
    from private_workspaces import provision_workspace
    from workspace_context import user_scope
    provision_workspace(accounts.left.id)
    with _session(accounts, accounts.left) as session:
        session.add(m.Founder(id="cached", name="Secret", email="secret@example.test"))
        session.commit()
        cached = session.get(m.Founder, "cached")
        assert cached.name == "Secret"  # Keep both identity-map entry and transaction live.
        actions = {
            "get": lambda: session.get(m.Founder, "cached"),
            "query_get": lambda: session.query(m.Founder).get("cached"),
            "execute": lambda: session.execute(sa.select(m.Founder)).all(),
            "scalar": lambda: session.scalar(sa.select(m.Founder)),
            "scalars": lambda: session.scalars(sa.select(m.Founder)).all(),
            "query": lambda: session.query(m.Founder).all(),
            "flush": session.flush, "connection": session.connection,
        }
        with user_scope(accounts.right.id), pytest.raises(RuntimeError, match="different workspace"):
            actions[operation]()
        assert session.get(m.Founder, "cached") is cached


def test_business_session_requires_context_and_context_resets(accounts):
    from workspace_context import current_user_id, user_scope
    with pytest.raises(RuntimeError, match="verified workspace identity"):
        accounts.SessionLocal()
    with user_scope(accounts.left.id):
        assert current_user_id() == accounts.left.id
        with pytest.raises(ValueError), user_scope(accounts.right.id):
            assert current_user_id() == accounts.right.id
            raise ValueError("synthetic")
        assert current_user_id() == accounts.left.id
    with pytest.raises(RuntimeError, match="verified workspace identity"):
        current_user_id()


@pytest.mark.parametrize("damage", ["registry_missing", "wrong_revision", "wrong_schema", "schema_missing"])
def test_broken_registry_never_falls_back_to_public_or_other_account(accounts, damage):
    import owner_auth as auth
    for person in accounts.people:
        assert _json(person.client.get("/v1/founders")) == []
    with accounts.engine.begin() as connection:
        condition = auth.workspaces.c.user_id == accounts.left.id
        if damage == "registry_missing":
            connection.execute(auth.workspaces.delete().where(condition))
        elif damage == "wrong_revision":
            connection.execute(auth.workspaces.update().where(condition).values(schema_revision="unknown"))
        elif damage == "wrong_schema":
            connection.execute(auth.workspaces.update().where(condition).values(schema_name="public"))
        else:
            connection.exec_driver_sql('DROP SCHEMA "' + accounts.left.schema + '" CASCADE')
    response = accounts.left.client.get("/v1/founders")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "private, no-store"
    assert _json(accounts.right.client.get("/v1/founders")) == []


def test_new_signups_never_adopt_held_public_rows(accounts):
    import db_models as m
    marker = "public-held-" + secrets.token_hex(8)
    before = _snapshot(accounts.engine, "public")
    try:
        with Session(accounts.engine) as session:
            session.add(m.Founder(id=marker, name="Held legacy founder", email=accounts.left.email))
            session.add(m.Thesis(id=marker, name="Held legacy thesis"))
            session.commit()
        held = _snapshot(accounts.engine, "public")
        for person in accounts.people:
            assert _json(person.client.get("/v1/founders")) == []
            assert _json(person.client.get("/v1/theses")) == []
            _json(person.client.get("/v1/founders/" + marker), 404)
            assert not any(_snapshot(accounts.engine, person.schema).values())
        assert _snapshot(accounts.engine, "public") == held
    finally:
        with accounts.engine.begin() as connection:
            connection.execute(m.Founder.__table__.delete().where(m.Founder.id == marker))
            connection.execute(m.Thesis.__table__.delete().where(m.Thesis.id == marker))
        assert _snapshot(accounts.engine, "public") == before


def test_operator_copy_uses_exact_subject_once_and_preserves_public(monkeypatch):
    """Optional, separately guarded DB: never copy the shared test public schema."""
    from alembic import command
    from alembic.config import Config
    import database
    import owner_auth as auth
    import private_workspaces as private
    url = os.environ.get("FOUNDEROS_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires a separate empty local founder_test migration database")
    parsed = sa.engine.make_url(url)
    assert parsed.database == "founder_test" and parsed.database != database.engine.url.database
    assert parsed.host is None
    assert str(parsed.query.get("host", "")).startswith("/private/tmp/founder-pg-test-")
    engine = sa.create_engine(url)
    roles = []
    owned = False
    try:
        with engine.connect() as connection:
            assert not sa.inspect(connection).get_table_names(schema="public"), "Migration DB must be empty"
            assert connection.execute(sa.text(
                "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'founderos_user_%'"
            )).all() == []
        owned = True
        backend = Path(__file__).resolve().parents[1]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "alembic"))
        monkeypatch.setenv("DATABASE_URL", url)
        command.upgrade(config, "f8a9b0c1d2e3")
        # Remove historical demo seeds only in this empty, test-owned DB.
        with engine.begin() as connection:
            connection.exec_driver_sql("TRUNCATE " + ", ".join("public." + name for name in sorted(TABLES)) + " CASCADE")
        with Session(engine) as session:
            _seed_all_tables(session, "synthetic-legacy")
        before = _snapshot(engine, "public")
        assert all(len(rows) == 1 for rows in before.values())
        command.upgrade(config, "92f61ac480db")
        assert _snapshot(engine, "public") == before
        with engine.begin() as connection:
            for user_id, subject in ((1001, "synthetic-verified-subject"), (1002, "synthetic-other-subject")):
                connection.execute(auth.owner.insert().values(id=user_id, google_sub=subject,
                    email="same@example.test", created_at=auth._now()))
                roles.append(private.role_for_user(connection, user_id))
        monkeypatch.setattr(database, "engine", engine)
        private.provision_workspace(1002)
        assert not any(_snapshot(engine, private.schema_for_user(1002)).values())
        # Refuse a nonempty destination before any successful copy.
        with Session(engine.execution_options(schema_translate_map={None: private.schema_for_user(1002)})) as session:
            import db_models as m
            session.add(m.Founder(id="already-live", name="Live", email="live@example.test"))
            session.commit()
        with pytest.raises(auth._Unavailable):
            private.copy_legacy_to_verified_owner("synthetic-other-subject", "same@example.test")
        result = private.copy_legacy_to_verified_owner("synthetic-verified-subject", "SAME@example.test")
        assert result == {"user_id": 1001, "tables_preserved": 13, "rows_preserved": 13}
        assert _snapshot(engine, private.schema_for_user(1001)) == before
        for subject in ("synthetic-verified-subject", "synthetic-other-subject"):
            with pytest.raises(auth._Unavailable):
                private.copy_legacy_to_verified_owner(subject, "same@example.test")
        assert _snapshot(engine, "public") == before
        assert len(_snapshot(engine, private.schema_for_user(1002))["founders"]) == 1
        with engine.connect() as connection:
            copied = connection.execute(sa.select(auth.workspaces.c.user_id).where(
                auth.workspaces.c.legacy_copied.is_(True))).scalars().all()
            assert copied == [1001]
    finally:
        if owned:
            with engine.begin() as connection:
                for user_id in (1001, 1002):
                    connection.exec_driver_sql('DROP SCHEMA IF EXISTS "' + private.schema_for_user(user_id) + '" CASCADE')
                connection.exec_driver_sql("DROP SCHEMA public CASCADE")
                connection.exec_driver_sql("CREATE SCHEMA public")
                for role in roles:
                    if connection.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}).first():
                        connection.exec_driver_sql('DROP OWNED BY "' + role + '"')
                        connection.exec_driver_sql('DROP ROLE "' + role + '"')
        engine.dispose()
