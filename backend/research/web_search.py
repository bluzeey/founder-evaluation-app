"""Routing helper for web-search backends.

Agents can use native Umans web search (via ``tools: [web_search]``), Tavily
(pre-fetch results and inject them into the prompt), or no web search at all.
This module centralizes the switching logic so each agent doesn't duplicate it.
"""
import logging
from typing import Optional, Tuple

from .tavily_client import TavilyClient

logger = logging.getLogger(__name__)


def prepare_web_search(
    query: str,
    provider: str,
    enabled: bool,
) -> Tuple[Optional[str], bool]:
    """Prepare web search context for an agent request.

    Args:
        query: Search query to run when using Tavily.
        provider: Web search backend name. One of ``native``, ``tavily``, ``none``.
        enabled: Whether web search is enabled for this agent.

    Returns:
        A tuple ``(context, use_native_tools)``. ``context`` is a text block to
        inject into the prompt (``None`` when using native tools or disabled).
        ``use_native_tools`` is ``True`` when the caller should send
        ``tools: [{"type": "web_search"}]`` to the Umans API.
    """
    if not enabled:
        return None, False

    provider = (provider or "native").lower()

    if provider == "tavily":
        try:
            client = TavilyClient()
            data = client.search(query)
            context = TavilyClient.format_results(data)
            logger.info(
                "web_search.tavily.query query=%s results=%s",
                query,
                len(data.get("results", []) or []),
            )
            return context, False
        except Exception as exc:
            logger.warning("web_search.tavily_failed query=%s error=%s", query, exc)
            # Degrade gracefully: let the LLM answer from its training data
            # rather than fail the whole task because Tavily is down.
            return (
                "Web search results were unavailable. Use your existing knowledge.",
                False,
            )

    if provider == "native":
        logger.info("web_search.native.query query=%s", query)
        return None, True

    # provider == "none" or any other unsupported value.
    return None, False
