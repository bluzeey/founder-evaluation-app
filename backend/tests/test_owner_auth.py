"""Offline auth integration tests: SQLite only, signed JWTs, mocked Google HTTP."""
import base64
import asyncio
import hashlib
import importlib.util
import io
import json
import secrets
import socket
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

import owner_auth as auth

ORIGIN = "https://founder-os-dev.vercel.app"
EMAIL = "owner@example.test"
BACKEND = Path(__file__).resolve().parents[1]
LEGACY_MIGRATION = BACKEND / "alembic/versions/e7f8a9b0c1d2_add_owner_auth.py"
MIGRATION = BACKEND / "alembic/versions/f8a9b0c1d2e3_public_google_identities.py"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Network is forbidden in owner auth tests")
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket.socket, "connect_ex", fail)


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def harness(monkeypatch, signing_key, request):
    for name, value in {
        "GOOGLE_CLIENT_ID": "unit-client", "GOOGLE_CLIENT_SECRET": "unit-secret",
        "REDIRECT_URI": ORIGIN + "/api/auth/google/callback",
        "FRONTEND_ORIGIN": ORIGIN, "WORKSPACE_MODE": "shared",
        "ALLOWED_EMAIL": EMAIL,  # Stale deployment config must have no effect.
    }.items():
        monkeypatch.setenv("FOUNDEROS_" + name, value)
    engine = sa.create_engine("sqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False})
    auth.AUTH_METADATA.create_all(engine)
    monkeypatch.setattr(auth, "_engine", lambda: engine)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def old_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "public, max-age=600"
        return response

    @app.get("/health")
    def health():
        return {"private": "must never escape"}

    active_user = ContextVar("auth_test_user", default=None)
    scope_events = []

    @contextmanager
    def data_access_scope(user_id):
        assert active_user.get() is None
        token = active_user.set(user_id)
        scope_events.append(("enter", user_id))
        try:
            yield
        finally:
            active_user.reset(token)
            scope_events.append(("exit", user_id, active_user.get()))

    @app.get("/private")
    def private(request: Request, q: str = ""):
        return {"private": True, "query": q, "user_id": request.state.user_id,
                "email": request.state.email, "owner_email": request.state.owner_email,
                "scoped_user_id": active_user.get()}

    @app.get("/async-principal")
    async def async_principal(request: Request):
        await asyncio.sleep(0)
        return {"user_id": request.state.user_id, "scoped_user_id": active_user.get()}

    @app.post("/write")
    def write():
        return {"written": True}

    @app.get("/failure")
    def failure():
        raise RuntimeError("sensitive internal failure")

    # Delegation lets each test supply/remove the trusted server hook before the
    # first request. It never comes from a request, cookie, header, or query.
    h = SimpleNamespace(data_access_scope=data_access_scope, scope_events=scope_events,
                        active_user=active_user)
    hook = getattr(request, "param", "default")
    if hook == "default":
        hook = lambda user_id: h.data_access_scope(user_id)
    auth.install_owner_auth(app, data_access_scope=hook)
    auth.install_owner_auth(app)  # idempotent, still the outermost user middleware
    h.__dict__.update(engine=engine, app=app, claims={}, calls=[],
                      provider_status=200, bad_signature=False, algorithm="RS256",
                      header_extra={}, access_queries=[], access_principals=[])

    class Google:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, *, data):
            assert url == auth.GOOGLE_TOKEN_URL
            assert data["client_secret"] == "unit-secret"
            assert data["redirect_uri"] == ORIGIN + "/api/auth/google/callback"
            assert data["grant_type"] == "authorization_code"
            assert data["code_verifier"] == h.verifier
            h.calls.append(("POST", url))
            claims = {
                "iss": "https://accounts.google.com", "aud": "unit-client",
                "sub": "google-owner-sub", "email": EMAIL, "email_verified": True,
                "nonce": h.nonce, "exp": int(time.time()) + 300,
                "iat": int(time.time()),
            }
            claims.update(h.claims)
            for name in getattr(h, "omit_claims", []):
                claims.pop(name)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if h.bad_signature else signing_key
            if h.algorithm != "RS256":
                key = "not-a-real-secret-with-at-least-32-bytes"
            token = jwt.encode(claims, key, algorithm=h.algorithm,
                               headers={"kid": "unit-key", **h.header_extra})
            return httpx.Response(h.provider_status, json={"id_token": token},
                                  request=httpx.Request("POST", url))

        def get(self, url):
            assert url == auth.GOOGLE_JWKS_URL
            h.calls.append(("GET", url))
            key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
            key.update({"kid": "unit-key", "use": "sig", "alg": "RS256"})
            return httpx.Response(200, json={"keys": [key]}, request=httpx.Request("GET", url))

    def google_client(**kwargs):
        assert kwargs == {"timeout": 10.0, "follow_redirects": False, "trust_env": False}
        return Google()

    monkeypatch.setattr(auth.httpx, "Client", google_client)
    async def access_logger(scope, receive, send):
        await app(scope, receive, send)
        if scope["type"] == "http":
            h.access_queries.append(scope["query_string"])
            h.access_principals.append(dict(scope.get("state", {})))
            assert active_user.get() is None

    with TestClient(access_logger, base_url=ORIGIN, follow_redirects=False) as client:
        h.client = client
        yield h
    engine.dispose()


def start(h):
    response = h.client.get("/auth/login")
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.headers["location"]).query)
    with h.engine.connect() as connection:
        pending = connection.execute(sa.select(auth.oauth_states).where(
            auth.oauth_states.c.state_hash == auth._hash(params["state"][0]),
        )).mappings().one()
    h.nonce, h.verifier = params["nonce"][0], pending["pkce_verifier"]
    h.state = params["state"][0]
    h.browser = h.client.cookies.get(auth.STATE_COOKIE)
    return response, params


def callback(h, **params):
    return h.client.get("/auth/google/callback?" + urlencode({"state": h.state, "code": "unit-code", **params}))


def login(h):
    start(h)
    response = callback(h)
    assert response.status_code == 302
    assert response.headers["location"] == ORIGIN + "/"
    return response


def private_headers(response):
    for name in ("cache-control", "cdn-cache-control", "vercel-cdn-cache-control", "surrogate-control"):
        assert response.headers[name] == "private, no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert not any(name.startswith("access-control-") for name in response.headers)


@pytest.mark.parametrize("path", ["/private", "/v1/founders", "/docs", "/redoc", "/openapi.json",
                                  "/docs/oauth2-redirect", "/unknown", "/auth/unknown", "/auth/me", "/health/"])
def test_all_routes_fail_closed_without_session(harness, path):
    response = harness.client.get(path)
    assert response.status_code == 401
    private_headers(response)


def test_minimal_health_survives_missing_config_and_schema(harness, monkeypatch):
    monkeypatch.delenv("FOUNDEROS_GOOGLE_CLIENT_SECRET")
    auth.AUTH_METADATA.drop_all(harness.engine)
    response = harness.client.get("/health")
    assert response.json() == {"status": "ok"}
    assert harness.client.head("/health").content == b""
    assert harness.client.get("/private").status_code == 503


@pytest.mark.parametrize("name", ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REDIRECT_URI", "FRONTEND_ORIGIN", "WORKSPACE_MODE"])
def test_each_config_value_required(harness, monkeypatch, name):
    monkeypatch.delenv("FOUNDEROS_" + name)
    for path in ("/auth/login", "/private", "/auth/me"):
        response = harness.client.get(path)
        assert response.status_code == 503
        private_headers(response)
    assert not harness.calls


@pytest.mark.parametrize("name,value", [
    ("FRONTEND_ORIGIN", "http://founder-os-dev.vercel.app"),
    ("FRONTEND_ORIGIN", ORIGIN + "/"),
    ("REDIRECT_URI", "https://attacker.test/api/auth/google/callback"),
    ("WORKSPACE_MODE", ""), ("WORKSPACE_MODE", "SHARED"),
    ("WORKSPACE_MODE", "shared "), ("WORKSPACE_MODE", "public"),
])
def test_invalid_config_fails_closed(harness, monkeypatch, name, value):
    monkeypatch.setenv("FOUNDEROS_" + name, value)
    assert harness.client.get("/auth/login").status_code == 503


@pytest.mark.parametrize("table", [auth.owner, auth.oauth_states, auth.sessions])
def test_missing_schema_fails_closed(harness, table):
    table.drop(harness.engine)
    assert harness.client.get("/auth/login").status_code == 503
    assert not harness.calls


@pytest.mark.parametrize("table", [auth.owner, auth.oauth_states, auth.sessions])
def test_schema_loss_rejects_existing_sessions(harness, table):
    login(harness)
    table.drop(harness.engine)
    for path in ("/auth/me", "/private", "/docs"):
        response = harness.client.get(path)
        assert response.status_code == 503
        private_headers(response)


def test_pkce_nonce_cookies_hashes_and_success(harness):
    response, params = start(harness)
    assert params["scope"] == ["openid email profile"]
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["redirect_uri"] == [ORIGIN + "/api/auth/google/callback"]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(harness.verifier.encode()).digest()).rstrip(b"=").decode()
    assert params["code_challenge"] == [challenge]
    assert "unit-secret" not in response.headers["location"]
    for header in response.headers.get_list("set-cookie"):
        assert "Secure" in header and "HttpOnly" in header and "SameSite=lax" in header
        assert "Path=/" in header and "Domain=" not in header
    private_headers(response)
    response = callback(harness)
    assert response.status_code == 302
    session = harness.client.cookies.get(auth.SESSION_COOKIE)
    assert len(session) == 43
    assert harness.client.cookies.get(auth.STATE_COOKIE) is None
    session_cookie = next(h for h in response.headers.get_list("set-cookie") if h.startswith(auth.SESSION_COOKIE + "="))
    assert all(flag in session_cookie for flag in ("Secure", "HttpOnly", "Path=/", "SameSite=lax", f"Max-Age={auth.SESSION_TTL}"))
    assert "Domain=" not in session_cookie
    with harness.engine.connect() as connection:
        stored = connection.execute(sa.select(auth.sessions)).mappings().one()
        identity = connection.execute(sa.select(auth.owner)).mappings().one()
        assert stored["session_hash"] == auth._hash(session) != session
        assert stored["expires_at"] - stored["created_at"] == auth.SESSION_TTL
        assert identity["google_sub"] == "google-owner-sub"
        assert connection.execute(sa.select(sa.func.count()).select_from(auth.oauth_states)).scalar_one() == 0
    response = harness.client.get("/auth/me")
    assert response.json() == {"authenticated": True, "email": EMAIL,
                               "user_id": identity["id"], "workspace_mode": "shared"}
    assert harness.access_principals[-1] == {"user_id": identity["id"], "email": EMAIL, "owner_email": EMAIL}
    private_headers(response)
    response = harness.client.get("/private?q=preserved")
    assert response.json() == {"private": True, "query": "preserved", "user_id": identity["id"],
                               "email": EMAIL, "owner_email": EMAIL, "scoped_user_id": None}
    private_headers(response)
    assert harness.client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("kind", ["tampered", "missing", "wrong_browser", "missing_browser", "expired"])
def test_invalid_state_never_calls_provider(harness, kind):
    start(harness)
    params = {"state": harness.state}
    if kind == "tampered":
        params["state"] = secrets.token_urlsafe(32)
    elif kind == "missing":
        params["state"] = ""
    elif kind in {"wrong_browser", "missing_browser"}:
        harness.client.cookies.clear()
        if kind == "wrong_browser":
            harness.client.cookies.set(auth.STATE_COOKIE, secrets.token_urlsafe(32),
                                       domain="founder-os-dev.vercel.app", path="/")
    else:
        with harness.engine.begin() as connection:
            connection.execute(auth.oauth_states.update().values(expires_at=auth._now() - 1))
    response = callback(harness, **params)
    assert response.status_code == 400
    assert harness.client.cookies.get(auth.STATE_COOKIE) is None
    assert not harness.calls


def test_duplicate_state_or_code_rejected(harness):
    for extra in ("state", "code"):
        start(harness)
        response = harness.client.get("/auth/google/callback?" + urlencode({"state": harness.state, "code": "unit-code"}) + f"&{extra}=duplicate")
        assert response.status_code == 400
    assert not harness.calls


def test_state_one_use_even_with_restored_browser_cookie(harness):
    login(harness)
    count = len(harness.calls)
    harness.client.cookies.set(auth.STATE_COOKIE, harness.browser, domain="founder-os-dev.vercel.app", path="/")
    assert callback(harness).status_code == 400
    assert len(harness.calls) == count


@pytest.mark.parametrize("claims", [
    {"email": ""}, {"email": None}, {"email": "invalid"},
    {"email": " owner@example.test"}, {"email": "x" * 320 + "@example.test"},
    {"email_verified": False}, {"email_verified": "true"},
    {"nonce": "tampered"}, {"aud": "wrong-client"},
    {"aud": ["unit-client", "another-client"]}, {"azp": "wrong-client"},
    {"iss": "https://attacker.test"}, {"exp": 1}, {"iat": 9999999999},
    {"sub": ""}, {"sub": "x" * 256}, {"sub": 123}, {"nonce": None},
])
def test_oidc_claims_rejected_and_state_burned(harness, claims):
    start(harness)
    harness.claims.update(claims)
    response = callback(harness)
    assert response.status_code == 403
    assert harness.client.cookies.get(auth.SESSION_COOKIE) is None
    with harness.engine.connect() as connection:
        assert connection.execute(sa.select(sa.func.count()).select_from(auth.owner)).scalar_one() == 0
    count = len(harness.calls)
    harness.client.cookies.set(auth.STATE_COOKIE, harness.browser, domain="founder-os-dev.vercel.app", path="/")
    assert callback(harness).status_code == 400
    assert len(harness.calls) == count


@pytest.mark.parametrize("missing", ["nonce", "aud", "exp", "iss", "sub", "email", "email_verified", "iat"])
def test_required_claims(harness, missing):
    start(harness)
    harness.omit_claims = [missing]
    assert callback(harness).status_code == 403


def test_google_email_case_preserves_the_same_owner_identity(harness, monkeypatch):
    monkeypatch.setenv("FOUNDEROS_ALLOWED_EMAIL", "Owner@Example.Test")
    start(harness)
    harness.claims["email"] = "OWNER@example.TEST"
    assert callback(harness).status_code == 302
    assert harness.client.get("/auth/me").json()["email"] == EMAIL
    user_id = harness.client.get("/auth/me").json()["user_id"]
    harness.claims["email"] = "owner@example.test"
    login(harness)
    assert harness.client.get("/auth/me").json()["user_id"] == user_id


def test_signature_and_algorithm_validation(harness):
    for algorithm, bad_signature in (("RS256", True), ("HS256", False)):
        start(harness)
        harness.algorithm, harness.bad_signature = algorithm, bad_signature
        assert callback(harness).status_code == 403


def test_stable_subject_binding_and_session_rotation(harness):
    login(harness)
    user_id = harness.client.get("/auth/me").json()["user_id"]
    original = harness.client.cookies.get(auth.SESSION_COOKIE)
    login(harness)
    assert harness.client.cookies.get(auth.SESSION_COOKIE) != original
    with harness.engine.connect() as connection:
        assert connection.execute(sa.select(auth.sessions.c.revoked_at).where(
            auth.sessions.c.session_hash == auth._hash(original),
        )).scalar_one() is not None
    harness.claims["email"] = "new-address@example.test"
    login(harness)
    assert harness.client.get("/auth/me").json() == {
        "authenticated": True, "email": "new-address@example.test",
        "user_id": user_id, "workspace_mode": "shared",
    }
    with harness.engine.connect() as connection:
        assert connection.execute(sa.select(auth.owner.c.google_sub)).scalar_one() == "google-owner-sub"


def select_session(h, raw):
    h.client.cookies.clear()
    h.client.cookies.set(auth.SESSION_COOKIE, raw, domain="founder-os-dev.vercel.app", path="/")


@pytest.mark.parametrize("legacy_email", [None, "*", "someone-else@example.test"])
def test_two_google_accounts_have_independent_ids_sessions_and_logout(harness, monkeypatch, legacy_email):
    if legacy_email is None:
        monkeypatch.delenv("FOUNDEROS_ALLOWED_EMAIL")
    else:
        monkeypatch.setenv("FOUNDEROS_ALLOWED_EMAIL", legacy_email)
    login(harness)
    first = harness.client.get("/auth/me").json()
    first_session = harness.client.cookies.get(auth.SESSION_COOKIE)
    harness.client.cookies.clear()  # A second browser, not rotation in the first.
    harness.claims.update(sub="second-google-sub", email="ANOTHER@Other.Example.Test")
    login(harness)
    second_session = harness.client.cookies.get(auth.SESSION_COOKIE)
    second = harness.client.get("/auth/me").json()
    assert second == {"authenticated": True, "email": "another@other.example.test",
                      "user_id": second["user_id"], "workspace_mode": "shared"}
    assert first["user_id"] != second["user_id"]
    assert first_session != second_session
    for raw, profile in ((first_session, first), (second_session, second)):
        select_session(harness, raw)
        assert harness.client.get("/auth/me").json() == profile
        principal = harness.client.get("/private").json()
        assert principal["user_id"] == profile["user_id"]
        assert principal["email"] == principal["owner_email"] == profile["email"]
    assert harness.client.post("/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    select_session(harness, second_session)
    assert harness.client.get("/auth/me").status_code == 401
    select_session(harness, first_session)
    assert harness.client.get("/auth/me").json() == first
    with harness.engine.connect() as connection:
        assert connection.execute(sa.select(sa.func.count()).select_from(auth.owner)).scalar_one() == 2
        assert connection.execute(sa.select(sa.func.count()).select_from(auth.sessions).where(
            auth.sessions.c.revoked_at.is_(None),
        )).scalar_one() == 1


def test_reused_email_cannot_claim_another_subjects_principal(harness):
    login(harness)
    first = harness.client.get("/auth/me").json()
    first_session = harness.client.cookies.get(auth.SESSION_COOKIE)
    harness.client.cookies.clear()
    harness.claims.update(sub="different-google-sub", email=EMAIL.upper())
    login(harness)
    second = harness.client.get("/auth/me").json()
    second_session = harness.client.cookies.get(auth.SESSION_COOKIE)
    assert second["email"] == first["email"]
    assert second["user_id"] != first["user_id"]
    # Subsequent logins keep the new subject's own ID, even as email changes.
    login(harness)
    assert harness.client.get("/auth/me").json() == second
    harness.claims["email"] = "changed@example.test"
    login(harness)
    assert harness.client.get("/auth/me").json()["user_id"] == second["user_id"]
    select_session(harness, first_session)
    assert harness.client.get("/auth/me").json() == first
    with harness.engine.connect() as connection:
        rows = connection.execute(sa.select(auth.owner).order_by(auth.owner.c.id)).mappings().all()
        assert [(r["id"], r["google_sub"]) for r in rows] == [
            (first["user_id"], "google-owner-sub"), (second["user_id"], "different-google-sub")]
        assert connection.execute(sa.select(auth.sessions.c.owner_id).where(
            auth.sessions.c.session_hash == auth._hash(second_session),
        )).scalar_one() == second["user_id"]


@pytest.mark.parametrize("mode", [None, "", "PUBLIC", "private ", "shared,private"])
def test_missing_or_invalid_mode_denies_even_valid_sessions(harness, monkeypatch, mode):
    login(harness)
    if mode is None:
        monkeypatch.delenv("FOUNDEROS_WORKSPACE_MODE")
    else:
        monkeypatch.setenv("FOUNDEROS_WORKSPACE_MODE", mode)
    for path in ("/private?workspace_mode=shared", "/auth/me", "/auth/login", "/docs", "/unknown"):
        response = harness.client.get(path, headers={"FOUNDEROS_WORKSPACE_MODE": "shared"})
        assert response.status_code == 503
        private_headers(response)
    assert harness.scope_events == []


@pytest.mark.parametrize("harness", [None, False, "invalid-hook"], indirect=True)
def test_private_without_callable_hook_denies_all_business_routes(harness, monkeypatch):
    monkeypatch.setenv("FOUNDEROS_WORKSPACE_MODE", "private")
    login(harness)
    profile = harness.client.get("/auth/me").json()
    assert profile["authenticated"] is True and profile["workspace_mode"] == "private"
    for path in ("/private?workspace_mode=shared", "/docs", "/openapi.json", "/unknown", "/auth/unknown"):
        response = harness.client.get(path)
        assert response.status_code == 503
        private_headers(response)
    assert harness.client.post("/write", headers={"Origin": ORIGIN}).status_code == 503
    assert harness.client.post("/write").status_code == 503
    assert harness.client.post("/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    assert harness.client.get("/private").status_code == 503


@pytest.mark.parametrize("path,status", [
    ("/private", 200), ("/async-principal", 200), ("/unknown", 404),
    ("/docs", 200), ("/write", 405), ("/failure", 500),
])
def test_private_hook_wraps_downstream_and_resets_on_all_responses(harness, monkeypatch, path, status):
    monkeypatch.setenv("FOUNDEROS_WORKSPACE_MODE", "private")
    login(harness)
    profile = harness.client.get("/auth/me").json()
    assert harness.scope_events == []  # Profile/auth never enters the data scope.
    response = harness.client.get(path)
    assert response.status_code == status
    private_headers(response)
    if path in {"/private", "/async-principal"}:
        assert response.json()["user_id"] == response.json()["scoped_user_id"] == profile["user_id"]
    assert harness.scope_events == [("enter", profile["user_id"]), ("exit", profile["user_id"], None)]
    assert harness.active_user.get() is None


def test_private_hook_scopes_each_user_and_never_enters_on_denial(harness, monkeypatch):
    monkeypatch.setenv("FOUNDEROS_WORKSPACE_MODE", "private")
    login(harness)
    first = harness.client.get("/private").json()["scoped_user_id"]
    harness.client.cookies.clear()
    harness.claims.update(sub="other-sub", email=EMAIL)  # Email equality cannot select a scope.
    login(harness)
    second = harness.client.get("/private").json()["scoped_user_id"]
    assert first != second
    events = list(harness.scope_events)
    assert harness.client.post("/write", headers={"Origin": "https://attacker.test"}).status_code == 403
    harness.client.cookies.clear()
    assert harness.client.get("/private").status_code == 401
    assert harness.scope_events == events


@pytest.mark.parametrize("kind", ["returns-none", "factory-raises"])
def test_broken_private_scope_factory_fails_closed(harness, monkeypatch, kind):
    monkeypatch.setenv("FOUNDEROS_WORKSPACE_MODE", "private")
    login(harness)
    def broken(user_id):
        if kind == "factory-raises":
            raise RuntimeError("sensitive hook failure")
        return None
    harness.data_access_scope = broken
    response = harness.client.get("/private")
    assert response.status_code == 503
    assert "sensitive" not in response.text
    private_headers(response)


@pytest.mark.parametrize("ending", ["normal", "error", "cancel", "send-error"])
def test_private_scope_covers_stream_and_background_and_unwinds(harness, monkeypatch, ending):
    monkeypatch.setenv("FOUNDEROS_WORKSPACE_MODE", "private")
    login(harness)
    user_id = harness.client.get("/auth/me").json()["user_id"]
    raw = harness.client.cookies.get(auth.SESSION_COOKIE)
    observations = []

    async def downstream(scope, receive, send):
        observations.append(harness.active_user.get())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await asyncio.sleep(0)
        await send({"type": "http.response.body", "body": b"chunk", "more_body": True})
        if ending == "cancel":
            raise asyncio.CancelledError()
        if ending == "error":
            raise RuntimeError("stream failed")
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        observations.append(harness.active_user.get())  # Awaited background work.

    async def exercise():
        scope = {"type": "http", "method": "GET", "path": "/stream", "query_string": b"",
                 "headers": [(b"cookie", f"{auth.SESSION_COOKIE}={raw}".encode())]}
        async def receive():
            return {"type": "http.disconnect"}
        async def send(message):
            assert harness.active_user.get() == user_id
            if ending == "send-error" and message["type"] == "http.response.body":
                raise OSError("disconnected")
        middleware = auth._OwnerAuthMiddleware(downstream, harness.data_access_scope)
        try:
            await middleware(scope, receive, send)
        finally:
            assert harness.active_user.get() is None

    if ending == "normal":
        asyncio.run(exercise())
        assert observations == [user_id, user_id]
    else:
        expected = {"error": RuntimeError, "cancel": asyncio.CancelledError, "send-error": OSError}[ending]
        with pytest.raises(expected):
            asyncio.run(exercise())
        assert observations == [user_id]
    assert harness.scope_events[-2:] == [("enter", user_id), ("exit", user_id, None)]


@pytest.mark.parametrize("kind", ["missing", "malformed", "unknown", "expired", "revoked"])
def test_session_rejection(harness, kind):
    login(harness)
    if kind in {"missing", "malformed", "unknown"}:
        harness.client.cookies.clear()
        if kind != "missing":
            raw = "invalid" if kind == "malformed" else secrets.token_urlsafe(32)
            harness.client.cookies.set(auth.SESSION_COOKIE, raw, domain="founder-os-dev.vercel.app", path="/")
    else:
        with harness.engine.begin() as connection:
            values = {"expires_at": auth._now() - 1} if kind == "expired" else {"revoked_at": auth._now()}
            connection.execute(auth.sessions.update().values(**values))
    assert harness.client.get("/auth/me").status_code == 401
    assert harness.client.get("/private").status_code == 401


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("origin", [None, "null", "https://attacker.test", ORIGIN + "/", ORIGIN + ".attacker.test"])
def test_unsafe_methods_require_exact_origin(harness, method, origin):
    login(harness)
    headers = {} if origin is None else {"Origin": origin}
    response = harness.client.request(method, "/write", headers=headers)
    assert response.status_code == 403
    private_headers(response)


def test_valid_origin_and_logout_revoke_stolen_copy(harness):
    login(harness)
    stolen = harness.client.cookies.get(auth.SESSION_COOKIE)
    assert harness.client.post("/write", headers={"Origin": ORIGIN}).status_code == 200
    assert harness.client.get("/auth/logout").status_code == 405
    assert harness.client.post("/auth/logout").status_code == 403
    assert harness.client.get("/auth/me").status_code == 200
    response = harness.client.post("/auth/logout", headers={"Origin": ORIGIN})
    assert response.status_code == 204
    assert harness.client.cookies.get(auth.SESSION_COOKIE) is None
    private_headers(response)
    harness.client.cookies.set(auth.SESSION_COOKIE, stolen, domain="founder-os-dev.vercel.app", path="/")
    assert harness.client.get("/private").status_code == 401


def test_duplicate_origins_denied(harness):
    login(harness)
    assert harness.client.post("/write", headers=[("Origin", ORIGIN), ("Origin", ORIGIN)]).status_code == 403


def test_provider_failure_no_secrets_in_response_or_logs(harness, caplog):
    start(harness)
    harness.provider_status = 500
    response = callback(harness, code="credential-marker")
    assert response.status_code == 403
    combined = response.text + str(dict(response.headers)) + caplog.text
    for secret in ("credential-marker", "unit-secret", harness.state, harness.verifier):
        assert secret not in combined
    assert harness.access_queries[-1] == b""
    private_headers(response)


def test_provider_denial_consumes_state(harness):
    start(harness)
    assert callback(harness, error="access_denied").status_code == 400
    assert not harness.calls
    harness.client.cookies.set(auth.STATE_COOKIE, harness.browser, domain="founder-os-dev.vercel.app", path="/")
    assert callback(harness).status_code == 400


def test_failures_are_private_and_generic(harness):
    login(harness)
    response = harness.client.get("/failure")
    assert response.status_code == 500
    assert "sensitive" not in response.text
    private_headers(response)


def test_websockets_cannot_bypass_guard(harness):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with harness.client.websocket_connect("/private"):
            pytest.fail("WebSocket unexpectedly admitted")


def revision_module(path=MIGRATION):
    spec = importlib.util.spec_from_file_location("owner_auth_revision_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_migration_preserves_existing_auth_and_business_rows(monkeypatch):
    legacy, migration = revision_module(LEGACY_MIGRATION), revision_module()
    assert migration.down_revision == legacy.revision == "e7f8a9b0c1d2"
    config = Config(str(BACKEND / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == [migration.revision]
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE founders (id TEXT PRIMARY KEY, private_data TEXT)")
        connection.exec_driver_sql("INSERT INTO founders VALUES ('existing', 'unchanged')")
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(legacy, "op", operations)
        monkeypatch.setattr(migration, "op", operations)
        legacy.upgrade()
        connection.execute(auth.owner.insert().values(id=1, email=EMAIL, google_sub="legacy-sub", created_at=1))
        connection.execute(auth.sessions.insert().values(
            session_hash="a" * 64, owner_id=1, created_at=1, expires_at=9999999999))
        connection.execute(auth.oauth_states.insert().values(
            state_hash="b" * 64, browser_hash="c" * 64, nonce="d" * 43,
            pkce_verifier="e" * 43, expires_at=9999999999))
        original = {table.name: connection.execute(sa.select(table)).all()
                    for table in auth.AUTH_METADATA.tables.values()}
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert set(inspector.get_table_names()) == {"founders", *auth.AUTH_METADATA.tables}
        for table in auth.AUTH_METADATA.tables.values():
            columns = inspector.get_columns(table.name)
            assert [(c["name"], c["nullable"]) for c in columns] == [(c.name, c.nullable) for c in table.columns]
            assert {i["name"] for i in inspector.get_indexes(table.name)} == {i.name for i in table.indexes}
            assert connection.execute(sa.select(table)).all() == original[table.name]
        assert not inspector.get_check_constraints(auth.owner.name)
        assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints(auth.owner.name)} == {("google_sub",)}
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        # Round-trip the compatible singleton without deleting its session/state.
        migration.downgrade()
        migration.upgrade()
        for table in auth.AUTH_METADATA.tables.values():
            assert connection.execute(sa.select(table)).all() == original[table.name]
        connection.execute(auth.owner.insert().values(email=EMAIL, google_sub="new-sub", created_at=2))
        identities = connection.execute(sa.select(auth.owner).order_by(auth.owner.c.id)).mappings().all()
        assert [r["id"] for r in identities] == [1, 2]
        # The subject remains unique, while equal emails are accepted separately.
        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.execute(auth.owner.insert().values(email="different@example.test", google_sub="new-sub", created_at=3))
        with pytest.raises(RuntimeError, match="Cannot restore singleton"):
            migration.downgrade()
        assert connection.execute(sa.select(sa.func.count()).select_from(auth.owner)).scalar_one() == 2
        assert connection.exec_driver_sql("SELECT * FROM founders").all() == [("existing", "unchanged")]
    engine.dispose()


def test_public_migration_from_empty_applied_legacy_creates_no_default_identity(monkeypatch):
    engine = sa.create_engine("sqlite://")
    legacy, migration = revision_module(LEGACY_MIGRATION), revision_module()
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(legacy, "op", operations)
        monkeypatch.setattr(migration, "op", operations)
        legacy.upgrade()
        migration.upgrade()
        for table in auth.AUTH_METADATA.tables.values():
            assert connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one() == 0
        connection.execute(auth.owner.insert().values(email=EMAIL, google_sub="any-first-sub", created_at=1))
        connection.execute(auth.owner.insert().values(email="next@example.test", google_sub="next-sub", created_at=1))
        assert connection.execute(sa.select(auth.owner.c.id).order_by(auth.owner.c.id)).scalars().all() == [1, 2]
    engine.dispose()


def test_sqlite_migration_refuses_foreign_key_cascade_risk(monkeypatch):
    legacy, migration = revision_module(LEGACY_MIGRATION), revision_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(legacy, "op", operations)
        monkeypatch.setattr(migration, "op", operations)
        legacy.upgrade()
        connection.execute(auth.owner.insert().values(id=1, email=EMAIL, google_sub="old-sub", created_at=1))
        connection.execute(auth.sessions.insert().values(
            session_hash="a" * 64, owner_id=1, created_at=1, expires_at=9999999999))
        with pytest.raises(RuntimeError, match="foreign_keys=OFF"):
            migration.upgrade()
        assert connection.execute(sa.select(auth.sessions.c.owner_id)).scalars().all() == [1]
        assert sa.inspect(connection).get_check_constraints("owner_auth_identity")
    engine.dispose()


def test_postgres_public_migration_offline_sql_only_alters_auth_identity(monkeypatch):
    migration, output = revision_module(), io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    statements = [statement.strip().upper() for statement in sql.split(";") if statement.strip()]
    assert statements[:2] == [
        "ALTER TABLE OWNER_AUTH_IDENTITY DROP CONSTRAINT CK_OWNER_AUTH_SINGLE_OWNER",
        "ALTER TABLE OWNER_AUTH_IDENTITY DROP CONSTRAINT OWNER_AUTH_IDENTITY_EMAIL_KEY",
    ]
    assert len(statements) == 3
    sequence_sql = " ".join(statements[2].split())
    assert sequence_sql.startswith("SELECT SETVAL(")
    assert "COALESCE((SELECT MAX(ID) FROM OWNER_AUTH_IDENTITY), 0) + 1" in sequence_sql
    assert sequence_sql.count("PG_GET_SERIAL_SEQUENCE('OWNER_AUTH_IDENTITY', 'ID')") == 2
    assert "NEXTVAL(" in sequence_sql and sequence_sql.endswith("FALSE )")
