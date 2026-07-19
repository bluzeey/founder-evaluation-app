import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

from .api_lock import api_lock, is_web_search_enabled
from .http_utils import raise_for_status
from .prompts import FOUNDER_RESEARCH_SYSTEM_PROMPT
from .web_search import prepare_web_search

logger = logging.getLogger(__name__)

OPENAI_BASE_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
)


class OpenAIClient:
    """Client for the OpenAI chat completions endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5")
        self.timeout = float(timeout or os.environ.get("OPENAI_TIMEOUT", "60"))
        self.max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", "8000"))
        self.enable_web_search = is_web_search_enabled(
            "OPENAI_ENABLE_WEB_SEARCH_RESEARCH", "true"
        )

        logger.info(
            "openai_client.configured model=%s timeout=%s max_tokens=%s web_search=%s",
            self.model,
            self.timeout,
            self.max_tokens,
            self.enable_web_search,
        )

    def research(self, query: str, channels: List[str]) -> dict[str, Any]:
        """Research a founder using Tavily-backed web search + OpenAI reasoning.

        Args:
            query: Free-text founder description (name, company, location, etc.).
            channels: Channels to search, e.g. ["linkedin", "twitter", "github", "news"].

        Returns:
            Parsed JSON dict with keys: profile, summary, sources, evidence.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "openai_client.research.start query=%s channels=%s",
            query,
            channels,
        )
        user_message = (
            f"Research this founder across these channels: {', '.join(channels)}.\n\n"
            f"Query: {query}"
        )

        web_search_context, _ = prepare_web_search(
            query, self.enable_web_search
        )
        if web_search_context:
            user_message += f"\n\n{web_search_context}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": FOUNDER_RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_completion_tokens": self.max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            logger.info(
                "openai_client.research.request query=%s model=%s enable_web_search=%s",
                query,
                self.model,
                self.enable_web_search,
            )
            with api_lock():
                response = client.post(OPENAI_BASE_URL, headers=headers, json=payload)
            raise_for_status(response)
            data = response.json()

        parsed = self._parse_response(data)
        logger.info(
            "openai_client.research.end query=%s profile_name=%s evidence=%s",
            query,
            parsed.get("profile", {}).get("name"),
            len(parsed.get("evidence", []) or []),
        )
        return parsed

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            logger.error("openai_client.parse.unexpected_response data=%s", data)
            raise ValueError(f"Unexpected OpenAI response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            logger.error("openai_client.parse.empty_content")
            raise ValueError("OpenAI response contained no content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("openai_client.parse.invalid_json content=%s", content)
            raise ValueError(f"OpenAI response was not valid JSON:\n{content}") from exc

        logger.info("openai_client.parse.ok")
        return parsed
