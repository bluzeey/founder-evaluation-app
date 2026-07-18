import json
import os
import re
from typing import Any, List, Optional

import httpx

from .prompts import FOUNDER_RESEARCH_SYSTEM_PROMPT

UMANS_BASE_URL = "https://api.code.umans.ai/v1/chat/completions"


class UmansClient:
    """Client for the Umans Code OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        websearch_provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("UMANS_API_KEY")
        if not self.api_key:
            raise RuntimeError("UMANS_API_KEY is not set")

        self.websearch_provider = websearch_provider or os.environ.get(
            "UMANS_WEBSEARCH_PROVIDER", "native"
        )
        self.model = model or os.environ.get("UMANS_MODEL", "umans-coder")
        self.timeout = float(timeout or os.environ.get("UMANS_RESEARCH_TIMEOUT", "60"))

    def research(self, query: str, channels: List[str]) -> dict[str, Any]:
        """Research a founder using Umans native/exa web search.

        Args:
            query: Free-text founder description (name, company, location, etc.).
            channels: Channels to search, e.g. ["linkedin", "twitter", "github", "news"].

        Returns:
            Parsed JSON dict with keys: profile, summary, sources, evidence.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Umans-Websearch-Provider": self.websearch_provider,
        }

        user_message = (
            f"Research this founder across these channels: {', '.join(channels)}.\n\n"
            f"Query: {query}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": FOUNDER_RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "tools": [{"type": "web_search"}],
            "max_completion_tokens": 8000,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(UMANS_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Unexpected Umans response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")

        # Some models put structured output inside markdown fences.
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            raise ValueError("Umans response contained no content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Umans response was not valid JSON:\n{content}") from exc

        return parsed
