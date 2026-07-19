"""Shared HTTP utilities for research agents calling external LLM APIs."""
import logging
from typing import Any

import httpx

from .api_lock import record_api_failure, record_api_success

logger = logging.getLogger(__name__)


def is_retryable_status(status_code: int) -> bool:
    """Return True for transient HTTP status codes that are worth retrying."""
    return status_code in {408, 429, 500, 502, 503, 504}


def log_http_error(response: httpx.Response) -> None:
    """Log full request/response details for debugging API failures."""
    try:
        body = response.text
    except Exception as exc:
        body = f"<could not read body: {exc}>"

    logger.error(
        "research.http_error status=%s method=%s url=%s headers=%s body=%s",
        response.status_code,
        response.request.method,
        response.request.url,
        dict(response.headers),
        body,
    )


def raise_for_status(response: httpx.Response) -> None:
    """Like httpx.Response.raise_for_status, but logs the response body on errors.

    Also updates the shared circuit-breaker counters: successes reset the failure
    counter; retryable failures increment it.
    """
    try:
        response.raise_for_status()
        record_api_success()
    except httpx.HTTPStatusError as exc:
        log_http_error(response)
        if is_retryable_status(response.status_code):
            record_api_failure()
        raise
