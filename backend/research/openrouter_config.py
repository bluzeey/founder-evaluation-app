"""Local-only OpenRouter configuration; readiness never probes a provider."""
import math
import os
import re
from dataclasses import dataclass, field
from typing import Optional

CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-5"
SETUP_PENDING = "AI setup pending"


class AISetupPending(RuntimeError):
    def __init__(self):
        super().__init__(SETUP_PENDING)


def get_api_key(override: Optional[str] = None) -> str:
    # Explicit constructor overrides remain useful for injected clients/tests.
    # Application callers use only OPENROUTER_API_KEY, never legacy credentials.
    key = (override if override is not None else os.environ.get("OPENROUTER_API_KEY", "")).strip()
    if not key or not key.isascii() or any(char.isspace() for char in key) or not key.isprintable():
        raise AISetupPending()
    return key


def normalize_model(model: Optional[str] = None) -> str:
    value = (model if model is not None else os.environ.get("OPENROUTER_MODEL", "")).strip()
    value = value or DEFAULT_MODEL
    if "/" not in value and re.fullmatch(r"(?:gpt-|chatgpt-|o[1-9])[A-Za-z0-9._:+-]*", value):
        value = f"openai/{value}"
    if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9][A-Za-z0-9._:+-]*", value):
        raise AISetupPending()
    return value


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str = field(repr=False)
    model: str
    timeout: float
    max_tokens: int


def load_config(api_key: Optional[str] = None, model: Optional[str] = None,
                timeout: Optional[float] = None, *, default_timeout: float = 60,
                default_max_tokens: int = 8000) -> OpenRouterConfig:
    key = get_api_key(api_key)
    model_name = normalize_model(model)
    try:
        timeout_value = float(timeout if timeout is not None else os.environ.get("OPENROUTER_TIMEOUT", default_timeout))
        max_tokens = int(os.environ.get("OPENROUTER_MAX_TOKENS", default_max_tokens))
        if not math.isfinite(timeout_value) or timeout_value <= 0 or max_tokens <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise AISetupPending() from None
    return OpenRouterConfig(key, model_name, timeout_value, max_tokens)


def readiness() -> dict:
    """Public interface for GET /v1/ai/config; contains no keys or raw settings.

    Enabled means locally configured, not a check of credits or key validity.
    Readiness does not grant permission to run automatic or manual work.
    """
    try:
        load_config()
        enabled = True
    except AISetupPending:
        enabled = False
    return {"enabled": enabled, "mode": "manual", "provider": "openrouter",
            "reason": None if enabled else "setup_pending",
            "message": None if enabled else SETUP_PENDING}
