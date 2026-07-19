import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

from .http_utils import raise_for_status
from .prompts import SOURCING_SYSTEM_PROMPT
from .umans_lock import is_web_search_enabled, umans_api_lock
from .web_search import prepare_web_search

logger = logging.getLogger(__name__)

UMANS_BASE_URL = "https://api.code.umans.ai/v1/chat/completions"


class SourcingAgent:
    """AI agent that discovers interesting founders matching an investment thesis."""

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

        # Always use native web search unless explicitly overridden.
        self.websearch_provider = websearch_provider or os.environ.get(
            "UMANS_WEBSEARCH_PROVIDER", "native"
        )
        self.model = model or os.environ.get("UMANS_SOURCING_MODEL", "umans-coder")
        self.timeout = float(timeout or os.environ.get("UMANS_RESEARCH_TIMEOUT", "60"))
        self.max_tokens = int(os.environ.get("UMANS_MAX_TOKENS", "8000"))
        self.enable_web_search = is_web_search_enabled(
            "UMANS_ENABLE_WEB_SEARCH_SOURCING", "true"
        )

        logger.info(
            "sourcing_agent.configured provider=%s model=%s timeout=%s max_tokens=%s web_search=%s",
            self.websearch_provider,
            self.model,
            self.timeout,
            self.max_tokens,
            self.enable_web_search,
        )

    def discover(
        self,
        sectors: List[str],
        stages: List[str],
        geographies: List[str],
        risk_appetite: str = "moderate",
        sources: Optional[List[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """Discover founders matching the given thesis parameters.

        Args:
            sectors: Target sectors, e.g. ["B2B SaaS", "AI Infrastructure"].
            stages: Target stages, e.g. ["pre-seed", "seed"].
            geographies: Target geographies, e.g. ["India", "Europe"].
            risk_appetite: Investor risk appetite string.
            sources: Optional list of source configs, e.g. [{"platform": "linkedin", "keywords": "..."}].

        Returns:
            Parsed JSON dict with key "recommendations".
        """
        logger.info(
            "sourcing_agent.discover.start sectors=%s stages=%s geographies=%s risk=%s sources=%s",
            sectors,
            stages,
            geographies,
            risk_appetite,
            sources,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Umans-Websearch-Provider": self.websearch_provider,
        }

        source_lines = []
        if sources:
            for s in sources:
                platform = s.get("platform", "web")
                keywords = s.get("keywords", "")
                source_lines.append(f"- {platform}: {keywords}")
        source_block = "\n".join(source_lines) if source_lines else "- Use web search"

        user_message = (
            f"Discover interesting founders for this thesis:\n"
            f"Sectors: {', '.join(sectors)}\n"
            f"Stages: {', '.join(stages)}\n"
            f"Geographies: {', '.join(geographies)}\n"
            f"Risk appetite: {risk_appetite}\n"
            f"Sources to search (platform + keywords):\n{source_block}\n"
            f"For each recommendation, include a 'source' field matching the platform that found it."
        )

        search_keywords = " ".join(
            [s.get("keywords", "") for s in sources or []]
        ) or ", ".join(sectors)
        search_query = (
            f"Interesting pre-seed/seed startup founders in {', '.join(geographies)} "
            f"working on {search_keywords}"
        )
        web_search_context, use_native_tools = prepare_web_search(
            search_query, self.websearch_provider, self.enable_web_search
        )
        if web_search_context:
            user_message += f"\n\n{web_search_context}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SOURCING_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_completion_tokens": self.max_tokens,
        }
        if use_native_tools:
            payload["tools"] = [{"type": "web_search"}]

        with httpx.Client(timeout=self.timeout) as client:
            logger.info(
                "sourcing_agent.discover.request provider=%s model=%s enable_web_search=%s native_tools=%s",
                self.websearch_provider,
                self.model,
                self.enable_web_search,
                use_native_tools,
            )
            with umans_api_lock():
                response = client.post(UMANS_BASE_URL, headers=headers, json=payload)
            raise_for_status(response)
            data = response.json()

        parsed = self._parse_response(data)
        recommendations = parsed.get("recommendations", []) or []
        logger.info(
            "sourcing_agent.discover.end recommendations=%s",
            len(recommendations),
        )
        return parsed

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            logger.error("sourcing_agent.discover.unexpected_response data=%s", data)
            raise ValueError(f"Unexpected Umans response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            logger.error("sourcing_agent.discover.empty_content")
            raise ValueError("Umans response contained no content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("sourcing_agent.discover.invalid_json content=%s", content)
            raise ValueError(f"Umans response was not valid JSON:\n{content}") from exc

        self._validate_recommendations(parsed)
        return parsed

    def _validate_recommendations(self, parsed: dict[str, Any]) -> None:
        """Ensure recommendations contain the minimum fields for a real candidate."""
        recommendations = parsed.get("recommendations")
        if not isinstance(recommendations, list):
            logger.error(
                "sourcing_agent.discover.recommendations_not_list type=%s",
                type(recommendations).__name__,
            )
            raise ValueError("Response missing 'recommendations' list")

        if not recommendations:
            logger.warning("sourcing_agent.discover.empty_recommendations")
            raise ValueError("Sourcing agent returned empty recommendations")

        valid_count = 0
        for idx, rec in enumerate(recommendations):
            name = rec.get("name") if isinstance(rec, dict) else None
            source_url = rec.get("source_url") if isinstance(rec, dict) else None
            if name and source_url:
                valid_count += 1
            else:
                logger.warning(
                    "sourcing_agent.discover.invalid_recommendation idx=%s name=%s source_url=%s",
                    idx,
                    name,
                    source_url,
                )

        if valid_count == 0:
            logger.error(
                "sourcing_agent.discover.no_valid_recommendations count=%s",
                len(recommendations),
            )
            raise ValueError(
                "No valid recommendations: each recommendation needs a name and source_url"
            )

        logger.info(
            "sourcing_agent.discover.validated count=%s valid=%s",
            len(recommendations),
            valid_count,
        )
