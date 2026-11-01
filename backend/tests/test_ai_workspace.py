"""Offline actor-bound grants and worker workspace regressions (--noconftest)."""
import asyncio
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from fastapi import HTTPException
from starlette.requests import Request

from test_manual_ai import (
    isolated, create_case, clean_tables, TEST_USER_ID, OTHER_USER_ID, run_queued,
)
import ai_policy
import crud
import db_models
from celery_app import app as celery
from manual_test_helpers import ManualStore
from models import Founder
from tasks import document_extraction, enrichment_task, estimation_task, founder_pool, social_research
from workspace_context import current_user_id, user_scope


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-workspace-test-key")
    poison = Mock(side_effect=AssertionError("Network is forbidden"))
    monkeypatch.setattr(socket.socket, "connect", poison)
    monkeypatch.setattr(socket.socket, "connect_ex", poison)


@pytest.fixture
def grants(monkeypatch):
    store = ManualStore()
    monkeypatch.setattr(ai_policy, "_store", lambda: store)
    return store


def issue(store, workflow="estimate", target="same-target", actor=TEST_USER_ID):
    with user_scope(actor):
        return store.issue(workflow, target)


def test_queue_uses_context_and_overwrites_client_actor_and_intent(grants):
    task = SimpleNamespace(apply_async=Mock(return_value=SimpleNamespace(id="queued")))
    with user_scope(TEST_USER_ID):
        ai_policy.queue_manual_task(task, "estimate", "same-target", founder_id="same-target",
                                   manual_actor_id=OTHER_USER_ID, manual_intent="forged")
    call = task.apply_async.call_args.kwargs
    kwargs = call["kwargs"]
    assert kwargs["manual_actor_id"] == TEST_USER_ID
    assert kwargs["manual_intent"] != "forged"
    grant = json.loads(grants.get(f"manual-ai:grant:{kwargs['manual_intent']}"))
    assert grant["actor_id"] == TEST_USER_ID
    actor = ai_policy.manual_allowed(kwargs["manual_intent"], ("estimate",), "same-target",
                                     call["task_id"], TEST_USER_ID)
    assert type(actor) is int and actor == TEST_USER_ID
    assert json.loads(grants.get(f"manual-ai:task:{call['task_id']}"))["actor_id"] == TEST_USER_ID


def test_queue_and_status_without_identity_fail_before_redis(monkeypatch):
    poison = Mock(side_effect=AssertionError("No access without identity"))
    monkeypatch.setattr(ai_policy, "_store", poison)
    task = SimpleNamespace(apply_async=poison)
    for action in (lambda: ai_policy.queue_manual_task(task, "estimate", "same-target"),
                   lambda: ai_policy.task_status("unknown")):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 401
    poison.assert_not_called()


@pytest.mark.parametrize("actor", [None, False, True, 0, -1, "101", 101.0, 2**63, {}, []])
def test_invalid_or_missing_actor_cannot_use_a_grant(grants, actor):
    run = issue(grants)
    assert ai_policy.manual_allowed(run.intent, ("estimate",), "same-target", run.task_id, actor) is None


@pytest.mark.parametrize("field,value", [
    ("actor_id", None), ("actor_id", True), ("actor_id", 101.0), ("actor_id", "101"),
    ("actor_id", OTHER_USER_ID), ("intent", "different-intent"), ("workflow", "enrich"),
    ("target", "another-target"), ("task_id", "another-task"), ("expires_at", 0),
    ("expires_at", float("inf")),
])
def test_mismatched_grant_metadata_is_rejected(grants, field, value):
    run = issue(grants)
    key = f"manual-ai:grant:{run.intent}"
    grant = json.loads(grants.get(key))
    grant[field] = value
    grants.set(key, json.dumps(grant))
    assert ai_policy.manual_allowed(run.intent, ("estimate",), "same-target", run.task_id, TEST_USER_ID) is None


@pytest.mark.parametrize("raw", ["null", "[]", '"text"', "false", "1", "not-json"])
def test_malformed_grants_fail_closed(grants, raw):
    run = issue(grants)
    grants.set(f"manual-ai:grant:{run.intent}", raw)
    assert ai_policy.manual_allowed(run.intent, ("estimate",), "same-target", run.task_id, TEST_USER_ID) is None


def test_status_rejects_unknown_cross_user_and_legacy_tasks_before_results(grants, monkeypatch):
    task = SimpleNamespace(apply_async=Mock())
    with user_scope(TEST_USER_ID):
        ai_policy.queue_manual_task(task, "estimate", "same-target")
    task_id = task.apply_async.call_args.kwargs["task_id"]
    result = Mock(return_value=SimpleNamespace(state="STARTED", result=None))
    monkeypatch.setattr(celery, "AsyncResult", result)
    with user_scope(OTHER_USER_ID):
        for requested_id in (task_id, "unknown"):
            with pytest.raises(HTTPException) as exc:
                ai_policy.task_status(requested_id)
            assert (exc.value.status_code, exc.value.detail) == (404, "Manual AI task not found")
    result.assert_not_called()
    with user_scope(TEST_USER_ID):
        assert ai_policy.task_status(task_id)["status"] == "running"
    result.assert_called_once_with(task_id)
    for grant in ({"task_id": task_id}, {"task_id": "another", "actor_id": TEST_USER_ID},
                  {"task_id": task_id, "actor_id": float(TEST_USER_ID)}):
        grants.set(f"manual-ai:task:{task_id}", json.dumps(grant))
        result.reset_mock()
        with user_scope(TEST_USER_ID), pytest.raises(HTTPException) as exc:
            ai_policy.task_status(task_id)
        assert exc.value.status_code == 404
        result.assert_not_called()


def request(user_id=None, method="POST", email="compat@example.test"):
    req = Request({"type": "http", "method": method})
    if user_id is not None:
        req.state.user_id = user_id
    if email:
        req.state.owner_email = email
    return req


def test_http_guard_requires_verified_id_and_matching_context():
    with user_scope(TEST_USER_ID):
        for req in (request(), request(OTHER_USER_ID), request(True), request("101")):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(ai_policy.require_manual_ai(req))
            assert exc.value.status_code == 401
        # owner_email is compatibility state, never an identity requirement.
        asyncio.run(ai_policy.require_manual_ai(request(TEST_USER_ID, email=None)))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ai_policy.require_manual_ai(request(TEST_USER_ID)))
    assert exc.value.status_code == 401


def test_missing_openrouter_key_blocks_even_valid_actors_and_legacy_keys(grants, monkeypatch):
    run = issue(grants)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    for key in ("OPENAI_API_KEY", "UMANS_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.setenv(key, "legacy-credential")
    poison = Mock(side_effect=AssertionError("No Redis before setup"))
    monkeypatch.setattr(ai_policy, "_store", poison)
    assert ai_policy.manual_allowed(run.intent, ("estimate",), "same-target", run.task_id, run.actor_id) is None
    with user_scope(TEST_USER_ID):
        with pytest.raises(HTTPException) as exc:
            ai_policy.queue_manual_task(SimpleNamespace(apply_async=poison), "estimate", "same-target")
        assert (exc.value.status_code, exc.value.detail) == (503, "AI setup pending")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(ai_policy.require_manual_ai(request(TEST_USER_ID)))
        assert exc.value.status_code == 503
        asyncio.run(ai_policy.require_manual_ai(request(TEST_USER_ID, "GET")))
    poison.assert_not_called()


WORKERS = [
    pytest.param(estimation_task.run_estimate, "estimate", {"founder_id": "same-target"}, id="estimate"),
    pytest.param(enrichment_task.enrich_founder_chain, "enrich", {"founder_id": "same-target"}, id="chain"),
    pytest.param(document_extraction.extract_document, "document", {"file_bytes_b64": "aGk=", "filename": "deck.txt", "opportunity_id": "same-target"}, id="document"),
    pytest.param(social_research.research_social_background, "social", {"founder_id": "same-target", "name": "Name", "email": "x@example.test", "linkedin_url": None, "github_url": None}, id="social"),
    pytest.param(founder_pool.refresh_pool_task, "source", {"thesis_id": "same-target"}, id="source"),
    pytest.param(founder_pool.refresh_founder_pool, "source", {"thesis_id": "same-target"}, id="source-child"),
    pytest.param(enrichment_task.enrich_social, "enrich", {"founder_id": "same-target"}, id="social-stage"),
    pytest.param(enrichment_task.enrich_deep_web, "enrich", {"founder_id": "same-target"}, id="web-stage"),
    pytest.param(enrichment_task.enrich_estimate, "enrich", {"founder_id": "same-target"}, id="estimate-stage"),
]


def deliver(task, run, params, **overrides):
    kwargs = {**params, "manual_intent": run.intent, "manual_actor_id": run.actor_id, **overrides}
    if hasattr(task, "push_request"):
        task.push_request(id=run.task_id, args=(), kwargs=kwargs, retries=0)
        try:
            return task.run(**kwargs)
        finally:
            task.pop_request()
    return task(**{"manual_task_id": run.task_id, **kwargs})


@pytest.mark.parametrize("task,workflow,params", WORKERS)
@pytest.mark.parametrize("forgery", ["actor", "missing-actor", "boolean-actor", "workflow", "target", "task_id", "intent", "expired"])
def test_every_worker_rejects_forgery_before_scope_db_or_provider(grants, monkeypatch, task, workflow, params, forgery):
    run = issue(grants, workflow)
    key = f"manual-ai:grant:{run.intent}"
    grant = json.loads(grants.get(key))
    overrides = {}
    if forgery == "actor":
        overrides["manual_actor_id"] = OTHER_USER_ID
    elif forgery == "missing-actor":
        overrides["manual_actor_id"] = None
    elif forgery == "boolean-actor":
        overrides["manual_actor_id"] = True
    else:
        grant[{"expired": "expires_at"}.get(forgery, forgery)] = 0 if forgery == "expired" else "forged"
        grants.set(key, json.dumps(grant))
    poison = Mock(side_effect=AssertionError("Rejected work accessed external state"))
    for module in (document_extraction, social_research, founder_pool, enrichment_task, estimation_task):
        monkeypatch.setattr(module, "user_scope", poison)
        if hasattr(module, "SessionLocal"):
            monkeypatch.setattr(module, "SessionLocal", poison)
    for module, attr in ((document_extraction, "DocumentAgent"), (social_research, "SocialAgent"),
                         (founder_pool, "SourcingAgent"), (founder_pool, "acquire_refresh_lock"),
                         (enrichment_task, "OpenAIClient"), (estimation_task, "estimate_founder_scores"),
                         (enrichment_task, "estimate_founder_scores")):
        monkeypatch.setattr(module, attr, poison)
    # Even a stale ambient worker scope cannot rescue a forged message.
    with user_scope(OTHER_USER_ID):
        assert deliver(task, run, params, **overrides)["status"] == "skipped_manual_required"
        assert current_user_id() == OTHER_USER_ID
    poison.assert_not_called()


def test_social_worker_cannot_relabel_enrichment_grant_as_direct_delivery(grants, monkeypatch):
    run = issue(grants, "enrich")
    poison = Mock(side_effect=AssertionError("No DB"))
    monkeypatch.setattr(social_research, "SessionLocal", poison)
    params = dict(founder_id="same-target", name="Name", email="x@example.test", linkedin_url=None, github_url=None)
    assert deliver(social_research.research_social_background, run, params)["status"] == "skipped_manual_required"
    poison.assert_not_called()


def test_pool_lock_is_per_user_including_release(monkeypatch):
    keys = set()
    def set_lock(key, _value, **_kwargs):
        if key in keys:
            return False
        keys.add(key)
        return True
    client = SimpleNamespace(set=Mock(side_effect=set_lock), delete=Mock(side_effect=keys.discard))
    monkeypatch.setattr(founder_pool, "_redis_client", lambda: client)
    monkeypatch.setitem(celery.conf, "task_always_eager", False)
    with user_scope(TEST_USER_ID):
        assert founder_pool.acquire_refresh_lock()
        assert not founder_pool.acquire_refresh_lock()
    with user_scope(OTHER_USER_ID):
        assert founder_pool.acquire_refresh_lock()
        founder_pool.release_refresh_lock()
    assert keys == {f"{founder_pool.POOL_LOCK_KEY}:{TEST_USER_ID}"}
    with user_scope(TEST_USER_ID):
        founder_pool.release_refresh_lock()
    assert not keys
    for action in (founder_pool.acquire_refresh_lock, founder_pool.release_refresh_lock):
        with pytest.raises(RuntimeError):
            action()
    assert client.set.call_count == 3
    assert client.delete.call_count == 2


@pytest.mark.parametrize("workflow", ["estimate", "enrich", "document", "social", "source"])
def test_real_workflow_keeps_all_effects_in_grant_workspace(isolated, monkeypatch, workflow):
    fid, oid = create_case(isolated)
    # Identical record ids across workspaces make accidental fallback visible.
    with user_scope(OTHER_USER_ID), isolated.factory() as db:
        crud.create_founder(db, Founder(id=fid, name="Other workspace", email="other@example.test"))
    paths = {"estimate": f"/v1/founders/{fid}/estimate", "enrich": f"/v1/founders/{fid}/enrich",
             "document": f"/v1/opportunities/{oid}/deck/extract?founder_id={fid}",
             "social": f"/v1/founders/{fid}/research-social", "source": "/v1/founders/pool/refresh"}
    kwargs = {"files": {"file": ("deck.txt", b"Pitch", "text/plain")}} if workflow == "document" else {}
    response = isolated.client.post(paths[workflow], **kwargs)
    assert response.status_code == 200, response.text
    effects = []
    def observe(kind):
        actor = current_user_id()
        effects.append((kind, actor))
        assert actor == TEST_USER_ID
    def factory():
        observe("session-open")
        session = isolated.factory()
        close = session.close
        def scoped_close():
            observe("session-close")
            close()
        session.close = scoped_close
        return session
    for module in (document_extraction, social_research, founder_pool, enrichment_task):
        monkeypatch.setattr(module, "SessionLocal", factory)
    def agent(method, result):
        instance = SimpleNamespace()
        setattr(instance, method, Mock(side_effect=lambda *args, **kwargs: (observe(method), result)[1]))
        return Mock(side_effect=lambda: (observe("provider-init"), instance)[1])
    monkeypatch.setattr(document_extraction, "DocumentAgent", agent("extract", {"claims": [{"claim": "Only A claim"}], "evidence": []}))
    monkeypatch.setattr(social_research, "SocialAgent", agent("research", {"summary": "Only A social", "evidence": []}))
    monkeypatch.setattr(enrichment_task, "OpenAIClient", agent("research", {"summary": "Only A web", "sources": [], "evidence": []}))
    monkeypatch.setattr(founder_pool, "SourcingAgent", agent("discover", {"recommendations": [{"name": "Only A lead", "reason": "Evidence"}]}))
    def estimate(founder_id):
        observe("estimate")
        with factory() as db:
            crud.update_founder(db, founder_id, {"role": "Only A estimated"})
        return {"founder_score": 61, "overall_confidence": 0.2}
    monkeypatch.setattr(estimation_task, "estimate_founder_scores", estimate)
    monkeypatch.setattr(enrichment_task, "estimate_founder_scores", estimate)
    monkeypatch.setattr(founder_pool, "acquire_refresh_lock", lambda: (observe("lock"), True)[1])
    monkeypatch.setattr(founder_pool, "release_refresh_lock", lambda: observe("unlock"))
    tasks = {"estimate": estimation_task.run_estimate, "enrich": enrichment_task.enrich_founder_chain,
             "document": document_extraction.extract_document, "social": social_research.research_social_background,
             "source": founder_pool.refresh_pool_task}
    # Execute on another thread with no inherited request identity, as a worker.
    def execute():
        with pytest.raises(RuntimeError):
            current_user_id()
        result = run_queued(tasks[workflow])
        with pytest.raises(RuntimeError):
            current_user_id()
        return result
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(execute).result()["status"] == "completed"
    assert effects and all(actor == TEST_USER_ID for _, actor in effects)
    assert sum(kind == "session-open" for kind, _ in effects) == sum(kind == "session-close" for kind, _ in effects)
    with user_scope(OTHER_USER_ID), isolated.factory() as db:
        other = crud.get_founder(db, fid)
        assert other.name == "Other workspace" and other.role is None
        assert other.ai_research_summary is None and other.last_enriched_at is None
        assert db.query(db_models.Claim).count() == 0
        assert db.query(db_models.SocialMediaBackground).count() == 0
        assert db.query(db_models.FounderPoolItem).count() == 0


def test_estimate_retry_preserves_actor_and_restores_ambient_context(grants, monkeypatch):
    run = issue(grants)
    task = estimation_task.run_estimate
    kwargs = {"founder_id": "same-target", "manual_intent": run.intent, "manual_actor_id": run.actor_id}
    observed = []
    def fail(_founder_id):
        observed.append(current_user_id())
        raise RuntimeError("temporary failure")
    monkeypatch.setattr(estimation_task, "estimate_founder_scores", fail)
    send = Mock(return_value=SimpleNamespace(id=run.task_id))
    monkeypatch.setattr(task, "apply_async", send)
    # Exercise Celery's real retry serialization, with only broker delivery mocked.
    task.push_request(id=run.task_id, args=(), kwargs=kwargs, retries=0,
                      called_directly=False, is_eager=False, delivery_info={})
    try:
        with user_scope(OTHER_USER_ID):
            with pytest.raises(Retry):
                task.run(**kwargs)
            assert current_user_id() == OTHER_USER_ID
        with pytest.raises(RuntimeError):
            current_user_id()
    finally:
        task.pop_request()
    retry_kwargs = send.call_args.kwargs
    assert send.call_args.args[1] == kwargs
    assert retry_kwargs["task_id"] == run.task_id
    assert observed == [TEST_USER_ID]
    monkeypatch.setattr(estimation_task, "estimate_founder_scores", lambda _fid: {"founder_score": 42})
    with user_scope(OTHER_USER_ID):
        assert deliver(task, run, {"founder_id": "same-target"})["status"] == "completed"
        assert current_user_id() == OTHER_USER_ID
