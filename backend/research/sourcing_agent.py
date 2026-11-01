from typing import Any, List, Optional

from .api_lock import is_web_search_enabled
from .http_utils import chat_completion, parse_completion
from .openrouter_config import get_api_key, load_config
from .prompts import SOURCING_SYSTEM_PROMPT
from .web_search import prepare_web_search


class SourcingAgent:
    """AI agent that discovers interesting founders matching an investment thesis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key_override = api_key
        config = load_config(api_key, model, timeout, default_timeout=60, default_max_tokens=8000)
        self.api_key = config.api_key
        self.model = config.model
        self.timeout = config.timeout
        self.max_tokens = config.max_tokens
        self.enable_web_search = is_web_search_enabled(
            "OPENAI_ENABLE_WEB_SEARCH_SOURCING", "true"
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
        self.api_key = get_api_key(self._api_key_override)

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
        web_search_context = prepare_web_search(
            search_query, self.enable_web_search
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

        data = chat_completion(payload, api_key=self.api_key, timeout=self.timeout)

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_completion(data)
        self._validate_recommendations(parsed)
        return parsed

    def _validate_recommendations(self, parsed: dict[str, Any]) -> None:
        """Ensure recommendations contain the minimum fields for a real candidate."""
        recommendations = parsed.get("recommendations")
        if not isinstance(recommendations, list):
            raise ValueError("Response missing 'recommendations' list")
        if not recommendations:
            raise ValueError("Sourcing agent returned empty recommendations")
        if not any(isinstance(rec, dict) and rec.get("name") and rec.get("source_url")
                   for rec in recommendations):
            raise ValueError("No valid recommendations: each recommendation needs a name and source_url")
