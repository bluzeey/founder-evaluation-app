"""Web-search backend for research agents.

Search is handled by Tavily. The results are injected into the prompt sent to
OpenAI so the LLM can reason over real-time data without relying on provider-
specific search tools.
"""
import logging
from typing import Optional

from .tavily_client import TavilyClient

logger = logging.getLogger(__name__)


def prepare_web_search(query: str, enabled: bool) -> Optional[str]:
    """Fetch web search context via Tavily for an agent request.

    Args:
        query: Search query to run.
        enabled: Whether web search is enabled for this agent.

    Returns:
        A text block to inject into the prompt, or ``None`` when disabled.
        If Tavily fails, a graceful degradation message is returned so the
        LLM can still answer from its training data.
    """
    if not enabled:
        return None

    try:
        client = TavilyClient()
        data = client.search(query)
        context = TavilyClient.format_results(data)
        logger.info(
            "web_search.tavily.query query=%s results=%s",
            query,
            len(data.get("results", []) or []),
        )
        return context
    except Exception as exc:
        logger.warning("web_search.tavily_failed query=%s error=%s", query, exc)
        # Degrade gracefully: let the LLM answer from its training data
        # rather than fail the whole task because Tavily is down.
        return (
            "Web search results were unavailable. Use your existing knowledge."
        )
