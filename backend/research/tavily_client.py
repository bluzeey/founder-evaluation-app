"""Client for the Tavily search API.

Tavily fetches real-time search results, which are then injected into the
prompt sent to OpenAI. This keeps the heavy search step separate from the LLM
endpoint and avoids provider-specific web-search overload errors.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from .http_utils import raise_for_status

logger = logging.getLogger(__name__)

TAVILY_BASE_URL = "https://api.tavily.com/search"


class TavilyClient:
    """Thin client for Tavily's search endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY is not set")

        self.timeout = float(timeout or os.environ.get("TAVILY_TIMEOUT", "30"))
        self.max_results = int(
            max_results or os.environ.get("TAVILY_MAX_RESULTS", "5")
        )
        self.search_depth = search_depth or os.environ.get(
            "TAVILY_SEARCH_DEPTH", "basic"
        )

        logger.info(
            "tavily_client.configured timeout=%s max_results=%s search_depth=%s",
            self.timeout,
            self.max_results,
            self.search_depth,
        )

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
        include_answer: bool = False,
    ) -> Dict[str, Any]:
        """Run a Tavily search and return the raw response.

        Args:
            query: Search query.
            max_results: Override the default max results.
            search_depth: Override the default search depth (basic/advanced).
            include_answer: Whether to ask Tavily to provide a synthesized answer.

        Returns:
            Tavily JSON response with ``query`` and ``results`` keys.
        """
        logger.info(
            "tavily_client.search.start query=%s max_results=%s search_depth=%s",
            query,
            max_results or self.max_results,
            search_depth or self.search_depth,
        )

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth or self.search_depth,
            "max_results": max_results or self.max_results,
            "include_answer": include_answer,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(TAVILY_BASE_URL, json=payload)
            raise_for_status(response)
            data = response.json()

        results = data.get("results", []) or []
        logger.info(
            "tavily_client.search.end query=%s results=%s",
            data.get("query", query),
            len(results),
        )
        return data

    @staticmethod
    def format_results(data: Dict[str, Any]) -> str:
        """Format Tavily results into a concise text block for an LLM prompt."""
        results: List[Dict[str, Any]] = data.get("results", []) or []
        if not results:
            return "No web search results were found."

        lines = ["Web search results:"]
        for idx, result in enumerate(results, start=1):
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            content = result.get("content", "").strip()
            lines.append(f"{idx}. {title}")
            if url:
                lines.append(f"   URL: {url}")
            if content:
                lines.append(f"   Snippet: {content}")
            lines.append("")

        answer = data.get("answer")
        if answer:
            lines.append(f"Search summary: {answer}")

        return "\n".join(lines).strip()
