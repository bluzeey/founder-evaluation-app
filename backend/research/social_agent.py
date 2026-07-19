import json
import logging
import os
import re
import uuid
from typing import Any, List, Optional

import httpx

from .http_utils import raise_for_status
from .prompts import SOCIAL_RESEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

UMANS_BASE_URL = "https://api.code.umans.ai/v1/chat/completions"


class SocialAgent:
    """AI agent that researches a founder's LinkedIn/GitHub footprint."""

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
        self.model = model or os.environ.get("UMANS_SOCIAL_MODEL", "umans-coder")
        self.timeout = float(timeout or os.environ.get("UMANS_RESEARCH_TIMEOUT", "60"))
        self.max_tokens = int(os.environ.get("UMANS_MAX_TOKENS", "8000"))
        self.enable_web_search = os.environ.get("UMANS_ENABLE_WEB_SEARCH", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        logger.info(
            "social_agent.configured provider=%s model=%s timeout=%s max_tokens=%s web_search=%s",
            self.websearch_provider,
            self.model,
            self.timeout,
            self.max_tokens,
            self.enable_web_search,
        )

    def research(
        self,
        name: str,
        linkedin_url: Optional[str],
        github_url: Optional[str],
    ) -> dict[str, Any]:
        """Research a founder's social background.

        Args:
            name: Founder name.
            linkedin_url: LinkedIn profile URL, if provided.
            github_url: GitHub profile URL, if provided.

        Returns:
            Parsed JSON dict with keys: summary, footprints, evidence.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Umans-Websearch-Provider": self.websearch_provider,
        }

        logger.info(
            "social_agent.research.start name=%s has_linkedin=%s has_github=%s",
            name,
            bool(linkedin_url),
            bool(github_url),
        )
        user_message = f"Research this founder's social footprint.\nName: {name}"
        if linkedin_url:
            user_message += f"\nLinkedIn: {linkedin_url}"
        if github_url:
            user_message += f"\nGitHub: {github_url}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SOCIAL_RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_completion_tokens": self.max_tokens,
        }
        if self.enable_web_search:
            payload["tools"] = [{"type": "web_search"}]

        with httpx.Client(timeout=self.timeout) as client:
            logger.info("social_agent.research.request name=%s model=%s enable_web_search=%s", name, self.model, self.enable_web_search)
            response = client.post(UMANS_BASE_URL, headers=headers, json=payload)
            raise_for_status(response)
            data = response.json()

        parsed = self._parse_response(data)
        evidence = parsed.get("evidence", []) or []
        footprints = parsed.get("footprints", []) or []
        logger.info(
            "social_agent.research.end name=%s footprints=%s evidence=%s",
            name,
            len(footprints),
            len(evidence),
        )
        return parsed

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            logger.error("social_agent.parse.unexpected_response data=%s", data)
            raise ValueError(f"Unexpected Umans response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            logger.error("social_agent.parse.empty_content")
            raise ValueError("Umans response contained no content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("social_agent.parse.invalid_json content=%s", content)
            raise ValueError(f"Umans response was not valid JSON:\n{content}") from exc

        logger.info("social_agent.parse.ok")
        return parsed
