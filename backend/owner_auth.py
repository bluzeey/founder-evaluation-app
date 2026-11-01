"""Owner-only Google OIDC. Call install_owner_auth(app) LAST, before serving.

Requires all five FOUNDEROS_* settings below and the auth Alembic migration.
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

# Deliberately separate from business metadata: only the additive revision owns
# these tables. Future Alembic autogeneration must also include AUTH_METADATA.
AUTH_METADATA = sa.MetaData()
owner = sa.Table(
    "owner_auth_identity", AUTH_METADATA,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("email", sa.String(320), nullable=False, unique=True),
    sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("id = 1", name="ck_owner_auth_single_owner"),
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


class _Unavailable(Exception):
    pass


class _Denied(Exception):
    pass


@dataclass(frozen=True)
class _Config:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    frontend_origin: str
    allowed_email: str

    @classmethod
    def read(cls):
        values = [os.environ.get("FOUNDEROS_" + name, "") for name in (
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REDIRECT_URI",
            "FRONTEND_ORIGIN", "ALLOWED_EMAIL",
        )]
        if any(not value or value != value.strip() for value in values):
            raise _Unavailable()
        values[-1] = values[-1].casefold()
        config = cls(*values)
        origin = urlsplit(config.frontend_origin)
        if (origin.scheme != "https" or not origin.hostname or origin.username
                or origin.password or origin.path or origin.query or origin.fragment
                or config.redirect_uri != config.frontend_origin + "/api/auth/google/callback"
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", config.allowed_email)):
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
                or claims["email"].casefold() != config.allowed_email
                or claims.get("azp", config.client_id) != config.client_id
                or not isinstance(claims["nonce"], str)
                or not secrets.compare_digest(claims["nonce"].encode(), nonce.encode())
                or not isinstance(claims["sub"], str)
                or not claims["sub"] or len(claims["sub"]) > 255):
            raise _Denied()
        return claims["sub"]
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
    google_sub = _verify_google(codes[0], config, pending["pkce_verifier"], pending["nonce"])
    raw_session, now = secrets.token_urlsafe(32), _now()
    with _engine().begin() as connection:
        identity = connection.execute(sa.select(owner).where(owner.c.id == 1)).mappings().first()
        if identity is None:
            try:
                with connection.begin_nested():
                    connection.execute(owner.insert().values(
                        id=1, email=config.allowed_email, google_sub=google_sub, created_at=now,
                    ))
            except IntegrityError:
                pass  # A concurrent first login may have bound the singleton.
            identity = connection.execute(sa.select(owner).where(owner.c.id == 1)).mappings().one()
        if identity["email"] != config.allowed_email or identity["google_sub"] != google_sub:
            raise _Denied()
        previous = request.cookies.get(SESSION_COOKIE)
        if _opaque(previous):
            connection.execute(sessions.update().where(sessions.c.session_hash == _hash(previous))
                               .values(revoked_at=now))
        connection.execute(sessions.delete().where(sessions.c.expires_at <= now))
        connection.execute(sessions.insert().values(
            session_hash=_hash(raw_session), owner_id=1, created_at=now,
            expires_at=now + SESSION_TTL,
        ))
    response = RedirectResponse(config.frontend_origin + "/", status_code=302)
    _cookie(response, SESSION_COOKIE, raw_session, SESSION_TTL)
    return response


def _session_email(request, config):
    raw = request.cookies.get(SESSION_COOKIE)
    if not _opaque(raw):
        return None
    with _engine().connect() as connection:
        _schema_ready(connection)
        return connection.execute(sa.select(owner.c.email).select_from(sessions.join(owner)).where(
            sessions.c.session_hash == _hash(raw), sessions.c.expires_at > _now(),
            sessions.c.revoked_at.is_(None), owner.c.id == 1,
            owner.c.email == config.allowed_email,
        )).scalar_one_or_none()


def _handle_auth(request, config, params):
    path = request.scope["path"]
    try:
        if path == "/auth/login":
            return _login(request, config)
        if path == "/auth/google/callback":
            return _callback(request, config, params)
        email = _session_email(request, config)
        if email is None:
            return _error(401)
        if path == "/auth/me":
            return JSONResponse({"authenticated": True, "email": email})
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
    def __init__(self, app):
        self.app = app

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
                if method not in _SAFE_METHODS and origins != [config.frontend_origin]:
                    response = _error(403)
                elif path in {"/auth/login", "/auth/google/callback", "/auth/me", "/auth/logout"}:
                    expected = "POST" if path == "/auth/logout" else "GET"
                    response = (_error(405) if method != expected else
                                await run_in_threadpool(_handle_auth, request, config, params))
                else:
                    email = await run_in_threadpool(_session_email, request, config)
                    if email is None:
                        response = _error(401)
                    else:
                        downstream_scope.setdefault("state", {})["owner_email"] = email
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


def install_owner_auth(app):
    """Install LAST so this guard overrides CORS/cache middleware on every route.

    Auth routes are intercepted here, outside routing, so existing/future routes,
    mounts, docs, OpenAPI, and 404/405 responses all require an owner session.
    Health is always minimal. Misconfiguration or missing schema never bypasses
    authentication. There is deliberately no development or production bypass.
    """
    if getattr(app.state, "owner_auth_installed", False):
        return
    app.add_middleware(_OwnerAuthMiddleware)
    app.state.owner_auth_installed = True
