"""Readiness admission checks; SQLite/fake Redis, runnable with --noconftest."""
import asyncio
import json
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

# Reuse the isolated real-route harness without changing parent-owned fixtures.
from test_manual_ai import isolated, create_case, assert_quiet, clean_tables
import ai_policy
from workspace_context import user_scope

KEY = "sk-or-synthetic-readiness-test"


@pytest.fixture(autouse=True)
def no_key_or_external_access(monkeypatch):
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_TIMEOUT", "OPENROUTER_MAX_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai-secret")
    monkeypatch.setenv("UMANS_API_KEY", "legacy-umans-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "legacy-tavily-secret")
    monkeypatch.setattr(socket.socket, "connect", Mock(side_effect=AssertionError("No network")))
    monkeypatch.setattr(socket.socket, "connect_ex", Mock(side_effect=AssertionError("No network")))


def test_readiness_is_local_manual_dynamic_and_contains_no_secrets(monkeypatch):
    poison = Mock(side_effect=AssertionError("Readiness must be local"))
    monkeypatch.setattr(ai_policy, "_store", poison)
    assert ai_policy.readiness() == {"enabled": False, "mode": "manual", "provider": "openrouter",
                                     "reason": "setup_pending", "message": "AI setup pending"}
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    result = ai_policy.readiness()
    assert result["enabled"] is True
    assert result["mode"] == "manual"
    assert KEY not in json.dumps(result)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert ai_policy.readiness()["enabled"] is False
    poison.assert_not_called()


@pytest.mark.parametrize("name,value", [
    ("OPENROUTER_API_KEY", "  "), ("OPENROUTER_API_KEY", "unsafe\nheader"),
    ("OPENROUTER_MODEL", "https://untrusted.example.test/model"),
    ("OPENROUTER_TIMEOUT", "nan"), ("OPENROUTER_MAX_TOKENS", "-1"),
])
def test_invalid_settings_fail_closed_without_echoing_them(monkeypatch, name, value):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setenv(name, value)
    result = ai_policy.readiness()
    assert result["enabled"] is False
    assert result["message"] == "AI setup pending"
    assert KEY not in json.dumps(result)
    assert "untrusted" not in json.dumps(result)


@pytest.mark.parametrize("workflow", ["source", "social", "document", "estimate", "enrich"])
def test_no_key_rejects_before_creating_grants_or_queuing(monkeypatch, workflow):
    store = Mock(side_effect=AssertionError("No Redis"))
    task = SimpleNamespace(apply_async=Mock(side_effect=AssertionError("No queue")))
    monkeypatch.setattr(ai_policy, "_store", store)
    with pytest.raises(HTTPException) as raised:
        ai_policy.queue_manual_task(task, workflow, "target")
    assert raised.value.status_code == 503
    assert raised.value.detail == "AI setup pending"
    store.assert_not_called()
    task.apply_async.assert_not_called()


def request(method="POST", owner=True):
    req = Request({"type": "http", "method": method})
    if owner:
        req.state.owner_email = "owner@example.test"
        req.state.user_id = 1
    return req


def test_no_key_rejects_manual_http_work_but_keeps_status_readable():
    with user_scope(1):
        with pytest.raises(HTTPException) as raised:
            asyncio.run(ai_policy.require_manual_ai(request()))
        assert (raised.value.status_code, raised.value.detail) == (503, "AI setup pending")
        asyncio.run(ai_policy.require_manual_ai(request("GET")))
        with pytest.raises(HTTPException) as raised:
            asyncio.run(ai_policy.require_manual_ai(request(owner=False)))
        assert raised.value.status_code == 401


def test_readiness_does_not_alter_grant_matching_and_removed_key_blocks_workers(monkeypatch):
    from manual_test_helpers import ManualStore
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    store = ManualStore()
    access = Mock(return_value=store)
    monkeypatch.setattr(ai_policy, "_store", access)
    with user_scope(1):
        run = store.issue("enrich", "target")
    assert ai_policy.manual_allowed(run.intent, ("enrich",), "target", run.task_id, run.actor_id)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    access.reset_mock()
    assert not ai_policy.manual_allowed(run.intent, ("enrich",), "target", run.task_id, run.actor_id)
    access.assert_not_called()
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    assert ai_policy.manual_allowed(run.intent, ("enrich",), "target", run.task_id, run.actor_id)


@pytest.mark.parametrize("action", ["research", "source", "pool", "social", "estimate", "enrich", "document"])
def test_real_manual_routes_return_benign_503_without_providers_or_queue(isolated, monkeypatch, action):
    from research import web_search
    search = Mock(side_effect=AssertionError("No Tavily before setup"))
    monkeypatch.setattr(web_search, "TavilyClient", search)
    fid, oid = create_case(isolated)
    paths = {"research": "/v1/founders/research", "pool": "/v1/founders/pool/refresh",
             "social": f"/v1/founders/{fid}/research-social",
             "estimate": f"/v1/founders/{fid}/estimate", "enrich": f"/v1/founders/{fid}/enrich",
             "document": f"/v1/opportunities/{oid}/deck/extract?founder_id={fid}"}
    if action == "source":
        thesis = isolated.client.post("/v1/theses", json={"name": "Readiness thesis"}).json()
        paths[action] = f"/v1/theses/{thesis['id']}/source-now"
    kwargs = {"json": {"query": "Founder", "channels": ["news"]}} if action == "research" else {}
    if action == "document":
        kwargs = {"files": {"file": ("deck.txt", b"Deck", "text/plain")}}
    response = isolated.client.post(paths[action], **kwargs)
    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "AI setup pending"}
    assert_quiet(isolated)
    search.assert_not_called()


def test_data_views_and_plain_deck_save_continue_without_a_key(isolated):
    fid, oid = create_case(isolated)
    response = isolated.client.post(f"/v1/opportunities/{oid}/deck?founder_id={fid}",
                                    files={"file": ("deck.txt", b"Plain data", "text/plain")})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "saved"
    for path in ("/v1/founders", f"/v1/founders/{fid}", f"/v1/opportunities/{oid}/diligence"):
        assert isolated.client.get(path).status_code == 200
    assert_quiet(isolated)
