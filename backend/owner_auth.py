"""Public Google OIDC. Call install_owner_auth(app, data_access_scope=None) LAST.

Requires four Google/origin settings, an explicit server workspace mode, and the
auth Alembic migrations. Email is profile metadata, never a data ownership key.
Cookies belong to the browser-facing HTTPS host; the /api rewrite removes /api
before reaching this app. No redirect URL is derived from forwarding headers.
No tables are created at runtime and no Google tokens are persisted.
"""

import base64
import hashlib
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response


SESSION_COOKIE = "__Host-founderos_session"
STATE_COOKIE = "__Host-founderos_oauth"
SESSION_TTL = 12 * 60 * 60
STATE_TTL = 10 * 60
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_OPAQUE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_AUTH_PATHS = frozenset({"/auth/login", "/auth/google/callback", "/auth/me", "/auth/logout"})

# Deliberately separate from business metadata: only the additive revision owns
# these tables. Future Alembic autogeneration must also include AUTH_METADATA.
AUTH_METADATA = sa.MetaData()
owner = sa.Table(
    "owner_auth_identity", AUTH_METADATA,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("email", sa.String(320), nullable=False),
    sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
    sa.Column("created_at", sa.BigInteger, nullable=False),
)
oauth_states = sa.Table(
    "owner_auth_states", AUTH_METADATA,
    sa.Column("state_hash", sa.String(64), primary_key=True),
    sa.Column("browser_hash", sa.String(64), nullable=False),
    sa.Column("nonce", sa.String(43), nullable=False),
    sa.Column("pkce_verifier", sa.String(43), nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
)
sessions = sa.Table(
    "owner_auth_sessions", AUTH_METADATA,
    sa.Column("session_hash", sa.String(64), primary_key=True),
    sa.Column("owner_id", sa.Integer,
              sa.ForeignKey("owner_auth_identity.id", ondelete="CASCADE"), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    sa.Column("revoked_at", sa.BigInteger, nullable=True),
)
workspaces = sa.Table(
    "owner_auth_workspaces", AUTH_METADATA,
    sa.Column("user_id", sa.Integer,
              sa.ForeignKey("owner_auth_identity.id", ondelete="RESTRICT"), primary_key=True),
    sa.Column("schema_name", sa.String(63), nullable=False, unique=True),
    sa.Column("schema_revision", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("legacy_copied", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Index("uq_founderos_legacy_workspace", "legacy_copied", unique=True,
             postgresql_where=sa.text("legacy_copied IS TRUE"),
             sqlite_where=sa.text("legacy_copied IS 1")),
)


class _Unavailable(Exception):
    pass


class _Denied(Exception):
    pass


class WorkspaceMode(str, Enum):
    SHARED = "shared"
    PRIVATE = "private"


@dataclass(frozen=True)
class _Config:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    frontend_origin: str
    workspace_mode: WorkspaceMode

    @classmethod
    def read(cls):
        values = [os.environ.get("FOUNDEROS_" + name, "") for name in (
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REDIRECT_URI",
            "FRONTEND_ORIGIN", "WORKSPACE_MODE",
        )]
        if any(not value or value != value.strip() for value in values):
            raise _Unavailable()
        try:
            values[-1] = WorkspaceMode(values[-1])
        except ValueError:
            raise _Unavailable() from None
        config = cls(*values)
        origin = urlsplit(config.frontend_origin)
        if (origin.scheme != "https" or not origin.hostname or origin.username
                or origin.password or origin.path or origin.query or origin.fragment
                or config.redirect_uri != config.frontend_origin + "/api/auth/google/callback"):
            raise _Unavailable()
        return config


def _engine():
    # Lazy import also keeps isolated auth tests independent of business startup.
    from database import engine
    return engine


def _now():
    return int(time.time())


def _hash(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _opaque(value):
    return isinstance(value, str) and bool(_OPAQUE.fullmatch(value))


def _schema_ready(connection):
    for table in (owner, oauth_states, sessions):
        connection.execute(sa.select(table).limit(0))


def _cookie(response, name, value, ttl):
    response.set_cookie(name, value, max_age=ttl, path="/", secure=True,
                        httponly=True, samesite="lax")


def _clear_cookie(response, name):
    response.delete_cookie(name, path="/", secure=True, httponly=True, samesite="lax")


def _error(status):
    return JSONResponse({"detail": {
        400: "Invalid authentication response", 401: "Authentication required",
        403: "Access denied", 405: "Method not allowed",
        500: "Request failed", 503: "Authentication unavailable",
    }[status]}, status_code=status)


def _verify_google(code, config, verifier, nonce):
    """All provider I/O is server-only, fixed-host, and fails without details."""
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False, trust_env=False) as client:
            response = client.post(GOOGLE_TOKEN_URL, data={
                "code": code, "client_id": config.client_id,
                "client_secret": config.client_secret, "redirect_uri": config.redirect_uri,
                "grant_type": "authorization_code", "code_verifier": verifier,
            })
            response.raise_for_status()
            token = response.json()["id_token"]
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise _Denied()
            response = client.get(GOOGLE_JWKS_URL)
            response.raise_for_status()
            keys = [key for key in response.json()["keys"]
                    if key.get("kid") == header["kid"] and key.get("kty") == "RSA"
                    and key.get("use", "sig") == "sig"
                    and key.get("alg", "RS256") == "RS256"]
            if len(keys) != 1:
                raise _Denied()
            key = jwt.PyJWK.from_dict(keys[0], algorithm="RS256").key
            claims = jwt.decode(token, key, algorithms=["RS256"],
                                audience=config.client_id,
                                issuer=["https://accounts.google.com", "accounts.google.com"],
                                options={"strict_aud": True, "require": [
                                    "iss", "aud", "exp", "iat", "sub", "nonce",
                                    "email", "email_verified",
                                ]})
        if (claims.get("email_verified") is not True
                or not isinstance(claims.get("email"), str)
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", claims["email"])
                or len(claims["email"].casefold()) > 320
                or claims.get("azp", config.client_id) != config.client_id
                or not isinstance(claims["nonce"], str)
                or not secrets.compare_digest(claims["nonce"].encode(), nonce.encode())
                or not isinstance(claims["sub"], str)
                or not claims["sub"] or len(claims["sub"]) > 255):
            raise _Denied()
        return claims["sub"], claims["email"].casefold()
    except Exception:
        # Do not expose provider responses, authorization codes, or JWT claims.
        raise _Denied() from None


def _login(request, config):
    state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    now = _now()
    with _engine().begin() as connection:
        _schema_ready(connection)
        connection.execute(oauth_states.delete().where(oauth_states.c.expires_at <= now))
        connection.execute(oauth_states.insert().values(
            state_hash=_hash(state), browser_hash=_hash(browser), nonce=nonce,
            pkce_verifier=verifier, expires_at=now + STATE_TTL,
        ))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    response = RedirectResponse(GOOGLE_AUTHORIZE_URL + "?" + urlencode({
        "client_id": config.client_id, "redirect_uri": config.redirect_uri,
        "response_type": "code", "scope": "openid email profile", "state": state,
        "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
        "prompt": "select_account",
    }), status_code=302)
    _cookie(response, STATE_COOKIE, browser, STATE_TTL)
    return response


def _callback(request, config, params):
    states, codes = params.getlist("state"), params.getlist("code")
    browser = request.cookies.get(STATE_COOKIE)
    if len(states) != 1 or not _opaque(states[0]) or not _opaque(browser):
        return _error(400)
    # DELETE RETURNING commits before calling Google: parallel/replayed callbacks
    # can never reuse this state, including callbacks rejected by the provider.
    with _engine().begin() as connection:
        _schema_ready(connection)
        pending = connection.execute(oauth_states.delete().where(
            oauth_states.c.state_hash == _hash(states[0]),
            oauth_states.c.browser_hash == _hash(browser),
            oauth_states.c.expires_at > _now(),
        ).returning(oauth_states)).mappings().first()
    if pending is None or params.getlist("error") or len(codes) != 1 or not codes[0] or len(codes[0]) > 4096:
        return _error(400)
    google_sub, email = _verify_google(codes[0], config, pending["pkce_verifier"], pending["nonce"])
    raw_session, now = secrets.token_urlsafe(32), _now()
    with _engine().begin() as connection:
        identity_query = sa.select(owner).where(owner.c.google_sub == google_sub)
        identity = connection.execute(identity_query).mappings().first()
        if identity is None:
            try:
                with connection.begin_nested():
                    connection.execute(owner.insert().values(
                        email=email, google_sub=google_sub, created_at=now,
                    ))
            except IntegrityError:
                # Only a competing insert of this exact immutable subject can
                # resolve the race. An email match must never bind a principal.
                if connection.execute(identity_query).mappings().first() is None:
                    raise
            identity = connection.execute(identity_query).mappings().one()
        if identity["email"] != email:
            connection.execute(owner.update().where(owner.c.id == identity["id"]).values(email=email))
        previous = request.cookies.get(SESSION_COOKIE)
        if _opaque(previous):
            connection.execute(sessions.update().where(sessions.c.session_hash == _hash(previous))
                               .values(revoked_at=now))
        connection.execute(sessions.delete().where(sessions.c.expires_at <= now))
        connection.execute(sessions.insert().values(
            session_hash=_hash(raw_session), owner_id=identity["id"], created_at=now,
            expires_at=now + SESSION_TTL,
        ))
    _set_principal(request, {"user_id": identity["id"], "email": email})
    response = RedirectResponse(config.frontend_origin + "/", status_code=302)
    _cookie(response, SESSION_COOKIE, raw_session, SESSION_TTL)
    return response


def _session_principal(request):
    raw = request.cookies.get(SESSION_COOKIE)
    if not _opaque(raw):
        return None
    with _engine().connect() as connection:
        _schema_ready(connection)
        return connection.execute(sa.select(owner.c.id.label("user_id"), owner.c.email)
                                  .select_from(sessions.join(owner)).where(
            sessions.c.session_hash == _hash(raw), sessions.c.expires_at > _now(),
            sessions.c.revoked_at.is_(None),
        )).mappings().one_or_none()


def _set_principal(request, principal):
    request.state.user_id = principal["user_id"]
    request.state.email = principal["email"]
    request.state.owner_email = principal["email"]  # Compatibility for manual guard.


def _handle_auth(request, config, params):
    path = request.scope["path"]
    try:
        if path == "/auth/login":
            return _login(request, config)
        if path == "/auth/google/callback":
            return _callback(request, config, params)
        principal = _session_principal(request)
        if principal is None:
            return _error(401)
        _set_principal(request, principal)
        if path == "/auth/me":
            return JSONResponse({"authenticated": True, **principal,
                                 "workspace_mode": config.workspace_mode.value})
        with _engine().begin() as connection:
            connection.execute(sessions.update().where(
                sessions.c.session_hash == _hash(request.cookies[SESSION_COOKIE]),
            ).values(revoked_at=_now()))
        response = Response(status_code=204)
        _clear_cookie(response, SESSION_COOKIE)
        _clear_cookie(response, STATE_COOKIE)
        return response
    except _Denied:
        return _error(403)
    except (SQLAlchemyError, _Unavailable):
        return _error(503)


class _OwnerAuthMiddleware:
    def __init__(self, app, data_access_scope=None):
        self.app = app
        self.data_access_scope = data_access_scope

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        path, method = scope["path"], scope["method"]
        params = request.query_params
        # Server access loggers use the original scope after the response. Give
        # downstream business routes a copy while removing queries from that log.
        downstream_scope = dict(scope)
        scope["query_string"] = b""
        started = False

        async def private_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                for name in list(headers):
                    if name.lower().startswith("access-control-"):
                        del headers[name]
                for name in ("Cache-Control", "CDN-Cache-Control", "Vercel-CDN-Cache-Control", "Surrogate-Control"):
                    headers[name] = "private, no-store"
                headers["Pragma"] = "no-cache"
                headers["Expires"] = "0"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Content-Type-Options"] = "nosniff"
                headers.add_vary_header("Cookie")
                if path == "/auth/google/callback":
                    clear = Response()
                    _clear_cookie(clear, STATE_COOKIE)
                    for name, value in clear.raw_headers:
                        if name == b"set-cookie":
                            headers.append("set-cookie", value.decode("latin-1"))
            await send(message)

        try:
            if path == "/health" and method in {"GET", "HEAD"}:
                response = JSONResponse({"status": "ok"}) if method == "GET" else Response()
            else:
                config = _Config.read()
                origins = request.headers.getlist("origin")
                if (path not in _AUTH_PATHS and config.workspace_mode is WorkspaceMode.PRIVATE
                        and not callable(self.data_access_scope)):
                    response = _error(503)
                elif method not in _SAFE_METHODS and origins != [config.frontend_origin]:
                    response = _error(403)
                elif path in _AUTH_PATHS:
                    expected = "POST" if path == "/auth/logout" else "GET"
                    response = (_error(405) if method != expected else
                                await run_in_threadpool(_handle_auth, request, config, params))
                else:
                    principal = await run_in_threadpool(_session_principal, request)
                    if principal is None:
                        response = _error(401)
                    else:
                        _set_principal(request, principal)
                        downstream_scope["state"] = scope["state"]
                        if config.workspace_mode is WorkspaceMode.PRIVATE:
                            # Enter in this ASGI task: ContextVars then propagate
                            # into downstream async handlers and threadpool jobs.
                            # Always unwind, including exceptions/cancellation.
                            try:
                                context = self.data_access_scope(principal["user_id"])
                                if not callable(getattr(context, "__enter__", None)) or not callable(getattr(context, "__exit__", None)):
                                    raise _Unavailable()
                            except Exception:
                                raise _Unavailable() from None
                            with context:
                                await self.app(downstream_scope, receive, private_send)
                        else:
                            await self.app(downstream_scope, receive, private_send)
                        return
            await response(scope, receive, private_send)
        except (SQLAlchemyError, _Unavailable):
            if started:
                raise
            await _error(503)(scope, receive, private_send)
        except Exception:
            if started:
                raise
            await _error(500)(scope, receive, private_send)


def install_owner_auth(app, data_access_scope=None):
    """Install LAST so this guard overrides CORS/cache middleware on every route.

    Auth routes are intercepted here, outside routing, so existing/future routes,
    mounts, docs, OpenAPI, and 404/405 responses all require a verified session.
    FOUNDEROS_WORKSPACE_MODE must be exactly 'shared' or 'private'. Shared mode
    grants every signed-in user access to existing business routes; configure it
    only after the human approves that data policy. No mode is selected here.

    Private mode requires data_access_scope(user_id), a synchronous context
    manager factory supplied by the data-policy owner. It must enforce private
    access, set/reset any ContextVars in try/finally, and propagate exceptions.
    The context wraps the entire downstream ASGI call (including streaming and
    background work awaited by the app). Detached tasks need their own policy.
    Auth/profile endpoints work without this hook; every business route is 503.
    Neither email nor user ID implicitly maps to any legacy business records.
    Health is always minimal. Misconfiguration or missing schema never bypasses
    authentication. There is deliberately no development or production bypass.
    """
    if getattr(app.state, "owner_auth_installed", False):
        return
    app.add_middleware(_OwnerAuthMiddleware, data_access_scope=data_access_scope)
    app.state.owner_auth_installed = True
