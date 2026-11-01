"""Mocked provider checks; runnable with --noconftest, no DB/broker/network."""
import json
import socket
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import document_agent, openai_client, social_agent, sourcing_agent
from research import founder_estimator, http_utils
from research.openrouter_config import (
    AISetupPending, CHAT_COMPLETIONS_URL, DEFAULT_MODEL, load_config, normalize_model,
)

KEY = "sk-or-synthetic-readiness-test"
CASES = [
    (openai_client, openai_client.OpenAIClient, lambda c: c.research("Founder", ["news"])),
    (sourcing_agent, sourcing_agent.SourcingAgent, lambda c: c.discover(["AI"], ["seed"], ["India"])),
    (social_agent, social_agent.SocialAgent, lambda c: c.research("Founder", None, None)),
    (document_agent, document_agent.DocumentAgent, lambda c: c.extract("Deck text", "deck.txt")),
    (founder_estimator, founder_estimator.AIFounderEstimator,
     lambda c: c.estimate(SimpleNamespace(id="f_test", name="Founder", current_company=None, role=None),
                          source_reason="Shipped product")),
]
RESULT = {"profile": {}, "summary": "Research", "evidence": [], "claims": [], "footprints": [],
          "recommendations": [{"name": "Founder", "source_url": "https://example.test/founder"}]}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_TIMEOUT", "OPENROUTER_MAX_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai-secret")
    monkeypatch.setenv("UMANS_API_KEY", "legacy-umans-secret")
    monkeypatch.setenv("OPENAI_MODEL", "legacy-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.example.test/leak")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://untrusted.example.test/leak")
    monkeypatch.setenv("OPENAI_ENABLE_WEB_SEARCH", "false")
    monkeypatch.setattr(socket.socket, "connect", Mock(side_effect=AssertionError("No network")))
    monkeypatch.setattr(socket.socket, "connect_ex", Mock(side_effect=AssertionError("No network")))
    monkeypatch.setattr(http_utils, "api_lock", nullcontext)
    monkeypatch.setattr(http_utils, "record_api_failure", Mock())
    monkeypatch.setattr(http_utils, "record_api_success", Mock())


def transport(monkeypatch, response):
    """Real httpx serialization over an in-memory transport only."""
    requests, options = [], []
    original = httpx.Client

    def handler(request):
        requests.append(request)
        return response(request) if callable(response) else response

    def client(**kwargs):
        options.append(kwargs)
        return original(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(http_utils.httpx, "Client", client)
    return requests, options


@pytest.mark.parametrize("module,client_type,invoke", CASES)
def test_all_clients_fixed_host_auth_model_and_safe_transport(monkeypatch, module, client_type, invoke):
    monkeypatch.setenv("OPENROUTER_API_KEY", f"  {KEY}  ")
    monkeypatch.setenv("OPENROUTER_MODEL", " gpt-5 ")
    requests, options = transport(monkeypatch, httpx.Response(200, json={
        "choices": [{"message": {"content": json.dumps(RESULT)}}],
    }))
    invoke(client_type())
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == CHAT_COMPLETIONS_URL
    assert request.method == "POST"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["content-type"] == "application/json"
    payload = json.loads(request.content)
    assert payload["model"] == "openai/gpt-5"
    assert KEY not in json.dumps(payload)
    assert "legacy" not in request.headers["authorization"]
    assert options[0]["trust_env"] is False
    assert options[0]["follow_redirects"] is False
    assert options[0]["timeout"] > 0


@pytest.mark.parametrize("module,client_type,invoke", CASES)
def test_no_openrouter_key_means_no_http_or_search(monkeypatch, module, client_type, invoke):
    http = Mock(side_effect=AssertionError("HTTP must be inactive"))
    search = Mock(side_effect=AssertionError("Search must be inactive"))
    monkeypatch.setattr(http_utils.httpx, "Client", http)
    if hasattr(module, "prepare_web_search"):
        monkeypatch.setattr(module, "prepare_web_search", search)
    monkeypatch.setenv("OPENAI_ENABLE_WEB_SEARCH", "true")
    with pytest.raises(AISetupPending, match="^AI setup pending$"):
        invoke(client_type())
    http.assert_not_called()
    search.assert_not_called()


@pytest.mark.parametrize("module,client_type,invoke", CASES)
def test_removing_key_also_stops_existing_clients_before_search(monkeypatch, module, client_type, invoke):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    client = client_type()
    monkeypatch.delenv("OPENROUTER_API_KEY")
    http = Mock(side_effect=AssertionError("HTTP must be inactive"))
    search = Mock(side_effect=AssertionError("Search must be inactive"))
    monkeypatch.setattr(http_utils.httpx, "Client", http)
    if hasattr(module, "prepare_web_search"):
        monkeypatch.setattr(module, "prepare_web_search", search)
    with pytest.raises(AISetupPending):
        invoke(client)
    http.assert_not_called()
    search.assert_not_called()


@pytest.mark.parametrize("module,client_type,invoke", CASES[:3])
def test_optional_tavily_text_is_added_only_after_configuration(monkeypatch, module, client_type, invoke):
    from research import web_search
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setenv("OPENAI_ENABLE_WEB_SEARCH", "true")
    for name in ("OPENAI_ENABLE_WEB_SEARCH_RESEARCH", "OPENAI_ENABLE_WEB_SEARCH_SOURCING",
                 "OPENAI_ENABLE_WEB_SEARCH_SOCIAL"):
        monkeypatch.delenv(name, raising=False)
    search = Mock()
    search.return_value.search.return_value = {"results": []}
    search.format_results.return_value = "Search evidence"
    monkeypatch.setattr(web_search, "TavilyClient", search)
    requests, _ = transport(monkeypatch, httpx.Response(200, json={
        "choices": [{"message": {"content": json.dumps(RESULT)}}],
    }))
    invoke(client_type())
    search.return_value.search.assert_called_once()
    payload = json.loads(requests[0].content)
    assert "Search evidence" in payload["messages"][1]["content"]


@pytest.mark.parametrize("value,expected", [
    (None, DEFAULT_MODEL), ("", DEFAULT_MODEL), ("   ", DEFAULT_MODEL),
    ("gpt-5", DEFAULT_MODEL), ("openai/gpt-5", DEFAULT_MODEL),
    (" openai/gpt-5 ", DEFAULT_MODEL), ("o3", "openai/o3"),
    ("anthropic/claude-sonnet-4", "anthropic/claude-sonnet-4"),
])
def test_model_normalization(value, expected):
    assert normalize_model(value) == expected


@pytest.mark.parametrize("value", ["https://attacker.test/model", "gpt-5\nAuthorization: secret",
                                   "model/with/path", "unknown", "openai/", "/gpt-5"])
def test_invalid_models_fail_without_echoing_settings(value):
    with pytest.raises(AISetupPending) as raised:
        normalize_model(value)
    assert str(raised.value) == "AI setup pending"


def test_defaults_ignore_legacy_credentials_models_and_settings(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setenv("OPENAI_TIMEOUT", "broken-legacy-setting")
    monkeypatch.setenv("OPENAI_MAX_TOKENS", "broken-legacy-setting")
    for _, cls, _ in CASES:
        client = cls()
        assert client.model == DEFAULT_MODEL
        assert client.api_key == KEY
    assert KEY not in repr(load_config())


@pytest.mark.parametrize("module,client_type,invoke", CASES)
@pytest.mark.parametrize("status", [301, 307, 401, 402, 429, 503])
def test_errors_redirects_and_logs_never_expose_keys(monkeypatch, caplog, module, client_type, invoke, status):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    requests, _ = transport(monkeypatch, httpx.Response(status, text=f"Authorization: Bearer {KEY}", headers={
        "location": f"https://untrusted.example.test/{KEY}", "x-echo": KEY, "retry-after": KEY,
    }))
    with pytest.raises(httpx.HTTPStatusError) as raised:
        invoke(client_type())
    assert len(requests) == 1
    exc = raised.value
    assert KEY not in str(exc) + caplog.text + str(exc.request.headers) + str(exc.response.headers)
    assert exc.response.content == b""
    assert "authorization" not in exc.request.headers
    assert exc.response.status_code == status
    assert exc.__cause__ is None
    if http_utils.is_retryable_status(status):
        http_utils.record_api_failure.assert_called_once()
    else:
        http_utils.record_api_failure.assert_not_called()


@pytest.mark.parametrize("module,client_type,invoke", CASES)
def test_transport_errors_are_generic_and_do_not_retain_authorization(monkeypatch, caplog, module, client_type, invoke):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)

    def timeout(request):
        raise httpx.ReadTimeout(f"Provider echoed {KEY}", request=request)

    transport(monkeypatch, timeout)
    with pytest.raises(httpx.RequestError) as raised:
        invoke(client_type())
    assert KEY not in str(raised.value) + str(raised.value.request.headers) + caplog.text
    assert raised.value.__cause__ is None


@pytest.mark.parametrize("module,client_type,invoke", CASES)
@pytest.mark.parametrize("data", [
    {"error": KEY}, {"choices": []}, {"choices": [{"message": {"content": KEY}}]},
    {"choices": [{"message": {"content": None}}]},
    {"choices": [{"message": {"content": "[]"}}]},
])
def test_response_errors_never_echo_provider_content(monkeypatch, caplog, module, client_type, invoke, data):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    transport(monkeypatch, httpx.Response(200, json=data))
    with pytest.raises(ValueError) as raised:
        invoke(client_type())
    assert KEY not in str(raised.value) + caplog.text
    assert raised.value.__cause__ is None


def test_invalid_outer_json_is_generic(monkeypatch, caplog):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    transport(monkeypatch, httpx.Response(200, text=KEY))
    with pytest.raises(ValueError) as raised:
        openai_client.OpenAIClient().research("Founder", [])
    assert KEY not in str(raised.value) + caplog.text


def test_numeric_retry_after_and_circuit_behavior_remain_available(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    transport(monkeypatch, httpx.Response(429, headers={"retry-after": "120"}))
    with pytest.raises(httpx.HTTPStatusError) as raised:
        openai_client.OpenAIClient().research("Founder", [])
    assert float(raised.value.response.headers["retry-after"]) == 120
    http_utils.record_api_failure.assert_called_once()
