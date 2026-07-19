import os
from unittest.mock import MagicMock, patch

import pytest
import httpx

from research.tavily_client import TavilyClient
from research.web_search import prepare_web_search


def test_tavily_client_requires_api_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
            TavilyClient()


def test_tavily_client_uses_env_key():
    with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-env"}, clear=True):
        client = TavilyClient()
        assert client.api_key == "tvly-env"


def test_tavily_client_search_hits_endpoint():
    client = TavilyClient(api_key="tvly-test")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "query": "AI agent founders",
        "results": [
            {"title": "Result 1", "url": "https://example.com/1", "content": "Snippet 1"},
            {"title": "Result 2", "url": "https://example.com/2", "content": "Snippet 2"},
        ],
    }

    mock_http_client = MagicMock()
    mock_http_client.post.return_value = mock_response

    with patch("httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value = mock_http_client
        result = client.search("AI agent founders")

    assert result["query"] == "AI agent founders"
    assert len(result["results"]) == 2
    mock_http_client.post.assert_called_once()


def test_tavily_client_format_results():
    data = {
        "query": "test",
        "results": [
            {"title": "Foo", "url": "https://foo.com", "content": "Foo content"},
            {"title": "Bar", "url": "https://bar.com", "content": "Bar content"},
        ],
    }
    formatted = TavilyClient.format_results(data)
    assert "Foo" in formatted
    assert "https://foo.com" in formatted
    assert "Foo content" in formatted
    assert "Bar" in formatted


def test_tavily_client_format_results_empty():
    formatted = TavilyClient.format_results({"query": "test", "results": []})
    assert "No web search results" in formatted


def test_prepare_web_search_native_uses_tools():
    context, use_native_tools = prepare_web_search(
        "AI founders", "native", enabled=True
    )
    assert context is None
    assert use_native_tools is True


def test_prepare_web_search_disabled():
    context, use_native_tools = prepare_web_search(
        "AI founders", "native", enabled=False
    )
    assert context is None
    assert use_native_tools is False


@patch("research.web_search.TavilyClient")
def test_prepare_web_search_tavily_returns_context(mock_tavily_cls):
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "query": "AI founders",
        "results": [
            {"title": "Result", "url": "https://example.com", "content": "Snippet"}
        ],
    }
    mock_tavily_cls.return_value = mock_client
    mock_tavily_cls.format_results.return_value = "formatted Result context"

    context, use_native_tools = prepare_web_search(
        "AI founders", "tavily", enabled=True
    )
    assert context == "formatted Result context"
    assert use_native_tools is False
    mock_client.search.assert_called_once()


@patch("research.web_search.TavilyClient")
def test_prepare_web_search_tavily_degrades_on_failure(mock_tavily_cls):
    mock_client = MagicMock()
    mock_client.search.side_effect = RuntimeError("tavily down")
    mock_tavily_cls.return_value = mock_client

    context, use_native_tools = prepare_web_search(
        "AI founders", "tavily", enabled=True
    )
    assert context is not None
    assert "unavailable" in context
    assert use_native_tools is False
