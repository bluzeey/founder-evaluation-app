"""Credential-safe HTTP and response handling shared by OpenRouter clients."""
import json
import logging
import math
import re
from typing import Any

import httpx

from .api_lock import api_lock, record_api_failure, record_api_success
from .openrouter_config import CHAT_COMPLETIONS_URL, get_api_key

logger = logging.getLogger(__name__)


def is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 429, 500, 502, 503, 504}


def log_http_error(response: httpx.Response) -> None:
    # Providers/proxies can echo Authorization in bodies, headers or locations.
    logger.error("research.http_error status=%s", response.status_code)


def raise_for_status(response: httpx.Response) -> None:
    """Keep circuit/retry semantics without retaining credential-bearing objects."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        pass
    else:
        record_api_success()
        return
    log_http_error(response)
    if is_retryable_status(response.status_code):
        record_api_failure()
    headers = {}
    # Retry code uses only a numeric Retry-After, never arbitrary provider text.
    try:
        retry_after = float(response.headers.get("retry-after", ""))
        if math.isfinite(retry_after) and retry_after >= 0:
            headers["retry-after"] = str(retry_after)
    except (ValueError, TypeError, OverflowError):
        pass
    request = httpx.Request("POST", CHAT_COMPLETIONS_URL)
    safe_response = httpx.Response(response.status_code, request=request, headers=headers)
    raise httpx.HTTPStatusError("AI provider request failed. Please try again later.",
                                request=request, response=safe_response) from None


def chat_completion(payload: dict[str, Any], *, api_key: str, timeout: float) -> dict[str, Any]:
    """Use the existing synchronous httpx style with a single fixed destination."""
    key = get_api_key(api_key)
    try:
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            with api_lock():
                response = client.post(CHAT_COMPLETIONS_URL, headers={
                    "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                }, json=payload)
            raise_for_status(response)
            try:
                data = response.json()
            except (ValueError, TypeError):
                raise ValueError("AI provider returned an invalid response.") from None
    except httpx.RequestError:
        # Do not retain the original request (with its Authorization header).
        logger.warning("research.transport_error")
        raise httpx.RequestError("AI provider is unavailable. Please try again later.",
                                 request=httpx.Request("POST", CHAT_COMPLETIONS_URL)) from None
    if not isinstance(data, dict):
        raise ValueError("AI provider returned an invalid response.")
    return data


def parse_completion(data: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON/fenced JSON without exposing raw provider content on errors."""
    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ValueError("AI provider returned an invalid response.") from None
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content).strip()
    if not content:
        raise ValueError("AI provider returned no content.")
    try:
        parsed = json.loads(content)
    except (ValueError, TypeError):
        raise ValueError("AI provider returned invalid JSON.") from None
    if not isinstance(parsed, dict):
        raise ValueError("AI provider returned an invalid response.")
    return parsed
