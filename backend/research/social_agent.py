from typing import Any, List, Optional

from .api_lock import is_web_search_enabled
from .http_utils import chat_completion, parse_completion
from .openrouter_config import get_api_key, load_config
from .prompts import SOCIAL_RESEARCH_SYSTEM_PROMPT
from .web_search import prepare_web_search


class SocialAgent:
    """AI agent that researches a founder's LinkedIn/GitHub footprint."""

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
            "OPENAI_ENABLE_WEB_SEARCH_SOCIAL", "false"
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
        self.api_key = get_api_key(self._api_key_override)
        user_message = f"Research this founder's social footprint.\nName: {name}"
        if linkedin_url:
            user_message += f"\nLinkedIn: {linkedin_url}"
        if github_url:
            user_message += f"\nGitHub: {github_url}"

        search_query = f"{name} founder social footprint"
        if linkedin_url:
            search_query += f" linkedin {linkedin_url}"
        if github_url:
            search_query += f" github {github_url}"
        web_search_context = prepare_web_search(
            search_query, self.enable_web_search
        )
        if web_search_context:
            user_message += f"\n\n{web_search_context}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SOCIAL_RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_completion_tokens": self.max_tokens,
        }

        data = chat_completion(payload, api_key=self.api_key, timeout=self.timeout)

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        return parse_completion(data)
