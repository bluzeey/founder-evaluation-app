"""Distributed lock + circuit breaker for the shared Umans API.

The backend runs multiple Celery task types (sourcing, social research, document
extraction) that all hit the same Umans account. This module serializes those
requests and opens a circuit breaker if the API starts returning 429s, so a
temporary overload does not turn into an endless retry storm.
"""
import logging
import os
import time
from contextlib import contextmanager
from typing import Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

UMANS_API_LOCK_KEY = os.environ.get("UMANS_API_LOCK_KEY", "umans_api_lock")
UMANS_API_LOCK_TTL_SECONDS = int(os.environ.get("UMANS_API_LOCK_TTL_SECONDS", "120"))
UMANS_API_LOCK_TIMEOUT_SECONDS = float(
    os.environ.get("UMANS_API_LOCK_TIMEOUT_SECONDS", "30")
)
UMANS_API_CALL_DELAY_SECONDS = float(
    os.environ.get("UMANS_API_CALL_DELAY_SECONDS", "0")
)
UMANS_API_LOCK_DISABLED = os.environ.get("UMANS_API_LOCK_DISABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)

UMANS_CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(
    os.environ.get("UMANS_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
)
UMANS_CIRCUIT_BREAKER_COOLDOWN_SECONDS = int(
    os.environ.get("UMANS_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "600")
)

CIRCUIT_BREAKER_OPEN_KEY = "umans_api_circuit_breaker_open"
CIRCUIT_BREAKER_FAILURES_KEY = "umans_api_circuit_breaker_failures"


class UmansAPIOverload(Exception):
    """Raised when the Umans API circuit breaker is open."""

    pass


def _redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def is_web_search_enabled(agent_env_var: str, agent_default: str = "true") -> bool:
    """Return whether web search is enabled for a specific agent.

    Per-agent environment variables take precedence over the legacy
    UMANS_ENABLE_WEB_SEARCH variable. This lets sourcing keep web search
    while social research disables it when LinkedIn/GitHub URLs are provided.

    Args:
        agent_env_var: e.g. UMANS_ENABLE_WEB_SEARCH_SOURCING.
        agent_default: Default value when neither the per-agent nor legacy var
            is set. "true" or "false".
    """
    legacy = os.environ.get("UMANS_ENABLE_WEB_SEARCH")
    if legacy is not None:
        default = "true" if legacy.lower() in ("true", "1", "yes") else "false"
    else:
        default = agent_default

    value = os.environ.get(agent_env_var, default)
    return value.lower() in ("true", "1", "yes")


def is_circuit_open() -> bool:
    """Return True if the circuit breaker is currently open."""
    try:
        client = _redis_client()
        return bool(client.exists(CIRCUIT_BREAKER_OPEN_KEY))
    except Exception as exc:
        logger.warning("umans_api.circuit_breaker.check_failed error=%s", exc)
        return False


def open_circuit() -> None:
    """Open the circuit breaker for the configured cooldown period."""
    try:
        client = _redis_client()
        client.set(
            CIRCUIT_BREAKER_OPEN_KEY,
            str(time.time()),
            ex=UMANS_CIRCUIT_BREAKER_COOLDOWN_SECONDS,
        )
        logger.warning(
            "umans_api.circuit_breaker.open cooldown=%s",
            UMANS_CIRCUIT_BREAKER_COOLDOWN_SECONDS,
        )
    except Exception as exc:
        logger.warning("umans_api.circuit_breaker.open_failed error=%s", exc)


def record_umans_failure() -> int:
    """Record a transient Umans API failure and open the circuit if needed.

    Returns the current consecutive failure count.
    """
    try:
        client = _redis_client()
        failures = client.incr(CIRCUIT_BREAKER_FAILURES_KEY)
        client.expire(CIRCUIT_BREAKER_FAILURES_KEY, UMANS_CIRCUIT_BREAKER_COOLDOWN_SECONDS)
        logger.warning("umans_api.circuit_breaker.failure count=%s", failures)
        if failures >= UMANS_CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            open_circuit()
        return int(failures)
    except Exception as exc:
        logger.warning("umans_api.circuit_breaker.record_failed error=%s", exc)
        return 0


def record_umans_success() -> None:
    """Reset the failure counter after a successful call."""
    try:
        client = _redis_client()
        client.delete(CIRCUIT_BREAKER_FAILURES_KEY)
    except Exception as exc:
        logger.warning("umans_api.circuit_breaker.reset_failed error=%s", exc)


@contextmanager
def umans_api_lock():
    """Acquire a distributed lock before making an Umans API call.

    Only one Umans API request can be in flight at a time across the whole
    backend. This prevents the account-level concurrency limits from being
    exhausted when sourcing, social research, and document extraction overlap.
    """
    if UMANS_API_LOCK_DISABLED:
        yield
        return

    if is_circuit_open():
        logger.warning("umans_api.circuit_breaker.blocked")
        raise UmansAPIOverload(
            "Umans API circuit breaker is open; temporary overload, retry later"
        )

    try:
        client = _redis_client()
    except Exception as exc:
        logger.warning("umans_api_lock.redis_unavailable error=%s", exc)
        # Degrade gracefully: proceed without the lock rather than fail the call.
        yield
        return

    lock: Optional[redis.lock.Lock] = None
    acquired = False
    try:
        lock = client.lock(
            UMANS_API_LOCK_KEY,
            timeout=UMANS_API_LOCK_TTL_SECONDS,
            thread_local=False,
        )
        logger.info(
            "umans_api_lock.wait key=%s timeout=%s",
            UMANS_API_LOCK_KEY,
            UMANS_API_LOCK_TIMEOUT_SECONDS,
        )
        acquired = lock.acquire(
            blocking=True,
            blocking_timeout=UMANS_API_LOCK_TIMEOUT_SECONDS,
        )
        if not acquired:
            logger.warning(
                "umans_api_lock.acquire_failed key=%s timeout=%s",
                UMANS_API_LOCK_KEY,
                UMANS_API_LOCK_TIMEOUT_SECONDS,
            )
            # Degrade gracefully instead of blocking forever.
            yield
            return

        logger.info(
            "umans_api_lock.acquired key=%s ttl=%s",
            UMANS_API_LOCK_KEY,
            UMANS_API_LOCK_TTL_SECONDS,
        )

        # Optional throttle between calls to leave headroom under rate limits.
        if UMANS_API_CALL_DELAY_SECONDS > 0:
            time.sleep(UMANS_API_CALL_DELAY_SECONDS)

        yield
    finally:
        if acquired and lock is not None:
            try:
                lock.release()
                logger.info("umans_api_lock.released key=%s", UMANS_API_LOCK_KEY)
            except redis.exceptions.LockError:
                # Lock may have expired or been taken over; not fatal.
                logger.warning("umans_api_lock.release_failed key=%s", UMANS_API_LOCK_KEY)
            except Exception as exc:
                logger.warning("umans_api_lock.release_failed error=%s", exc)
