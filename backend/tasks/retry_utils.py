"""Shared retry helpers for Celery tasks that call external LLM APIs."""
import logging
import os
import random
from typing import Any

import httpx

from research.http_utils import is_retryable_status

logger = logging.getLogger(__name__)

SOURCING_MAX_RETRIES = int(os.environ.get("SOURCING_MAX_RETRIES", "3"))
SOURCING_RETRY_BASE_DELAY = float(os.environ.get("SOURCING_RETRY_BASE_DELAY", "60"))

SOCIAL_RESEARCH_MAX_RETRIES = int(os.environ.get("SOCIAL_RESEARCH_MAX_RETRIES", "3"))
SOCIAL_RESEARCH_RETRY_BASE_DELAY = float(os.environ.get("SOCIAL_RESEARCH_RETRY_BASE_DELAY", "60"))

DOCUMENT_MAX_RETRIES = int(os.environ.get("DOCUMENT_MAX_RETRIES", "3"))
DOCUMENT_RETRY_BASE_DELAY = float(os.environ.get("DOCUMENT_RETRY_BASE_DELAY", "60"))

# Absolute floor for any retry countdown. Prevents the API's small Retry-After
# values (e.g. 2s) from causing a tight retry loop.
MIN_RETRY_DELAY_SECONDS = float(os.environ.get("MIN_RETRY_DELAY_SECONDS", "60"))


def retry_countdown(
    exc: Exception,
    task_self: Any,
    base_delay: float = SOURCING_RETRY_BASE_DELAY,
) -> float:
    """Compute the next retry countdown using exponential backoff + jitter.

    Honors the Retry-After header on 429 responses, but never goes below the
    configured minimum or our own exponential backoff. This prevents an
    overloaded API from tricking us into a fast retry loop.
    """
    request_count = task_self.request.retries
    api_retry_after = 0.0
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        retry_after = exc.response.headers.get("retry-after") or exc.response.headers.get("Retry-After")
        if retry_after:
            try:
                api_retry_after = max(MIN_RETRY_DELAY_SECONDS, float(retry_after))
            except ValueError:
                pass

    backoff = base_delay * (2 ** request_count)
    jitter = random.uniform(0, 0.5) * backoff
    return max(MIN_RETRY_DELAY_SECONDS, api_retry_after, backoff + jitter)


def should_retry(exc: Exception) -> bool:
    """Return False for client errors that will never succeed on retry."""
    if isinstance(exc, httpx.HTTPStatusError):
        return is_retryable_status(exc.response.status_code)
    return True


def maybe_retry(
    task_self: Any,
    exc: Exception,
    base_delay: float = SOURCING_RETRY_BASE_DELAY,
) -> None:
    """Retry the task if the exception is retryable, otherwise re-raise it."""
    if not should_retry(exc):
        status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning("task.no_retry status=%s error=%s", status_code, exc)
        raise exc

    countdown = retry_countdown(exc, task_self, base_delay=base_delay)
    logger.info("task.retry countdown=%s retries=%s error=%s", countdown, task_self.request.retries, exc)
    raise task_self.retry(exc=exc, countdown=countdown)
