"""Isolated manual-AI regressions: SQLite, fake Redis, mocked providers/queues.

Can run with --noconftest to avoid the repository's PostgreSQL integration fixture.
No broker, worker, OAuth, provider, or deployed service is contacted.
"""
import csv
import importlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("OPENAI_API_KEY", "manual-ai-test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import ai_policy
import crud
import database
import db_models
import main
from celery_app import app as celery
from founder_csv_import import REQUIRED_COLUMNS
from models import FounderPoolItem
from tasks import document_extraction, enrichment_task, estimation_task, founder_pool, social_research


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


@pytest.fixture(autouse=True)
def clean_tables():
    # Override the parent's PostgreSQL autouse fixture for this isolated module.
    yield


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def set(self, key, value, ex=None):
        self.values[key] = value
        self.expirations[key] = ex
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)


@pytest.fixture
def isolated(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    for module in (database, social_research, founder_pool, enrichment_task, document_extraction):
        monkeypatch.setattr(module, "SessionLocal", factory)
    store = FakeRedis()
    monkeypatch.setattr(ai_policy, "_store", lambda: store)
    providers = []
    for module, name in ((main, "OpenAIClient"), (social_research, "SocialAgent"),
                         (founder_pool, "SourcingAgent"), (document_extraction, "DocumentAgent"),
                         (enrichment_task, "OpenAIClient"), (estimation_task, "estimate_founder_scores"),
                         (enrichment_task, "estimate_founder_scores")):
        mock = Mock(side_effect=AssertionError(f"Unexpected provider: {name}"))
        monkeypatch.setattr(module, name, mock)
        providers.append(mock)
    tasks = [social_research.research_social_background, founder_pool.refresh_pool_task,
             estimation_task.run_estimate, enrichment_task.enrich_founder_chain, document_extraction.extract_document]
    queues = []
    for task in tasks:
        queue = Mock(side_effect=lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]))
        monkeypatch.setattr(task, "apply_async", queue)
        queues.append(queue)
    api = FastAPI()
    api.include_router(main.app.router)

    @api.middleware("http")
    async def synthetic_verified_owner(request, call_next):
        # Test-only stand-in for the parent owner middleware's verified state.
        if request.headers.get("x-test-owner") == "verified":
            request.state.owner_email = "owner@example.test"
        return await call_next(request)

    def db_dependency():
        with factory() as session:
            yield session

    api.dependency_overrides[database.get_db] = db_dependency
    with TestClient(api, headers={"x-test-owner": "verified"}) as client:
        yield SimpleNamespace(client=client, factory=factory, store=store, providers=providers, queues=queues)
    engine.dispose()


def create_case(env, **extra):
    response = env.client.post("/v1/founders", json={"name": "Manual founder", "email": "manual@example.test",
        "linkedin_url": "https://linkedin.com/in/manual", **extra})
    assert response.status_code == 200, response.text
    founder_id = response.json()["id"]
    response = env.client.post(f"/v1/opportunities/opp_manual/screen?founder_id={founder_id}")
    assert response.status_code == 200, response.text
    return founder_id, "opp_manual"


def assert_quiet(env):
    for mock in env.providers + env.queues:
        mock.assert_not_called()
    assert not env.store.values


def test_create_legacy_auto_inputs_and_all_views_are_quiet(isolated):
    fid, oid = create_case(isolated, auto_score=True, enrichment_policy="AUTO")
    client = isolated.client
    for path in ("/v1/founders", f"/v1/founders/{fid}", f"/v1/founders/{fid}/score",
                 f"/v1/opportunities/{oid}/diligence", "/v1/founders/pool", "/v1/sourcing/status",
                 "/v1/sourcing/schedules", "/v1/sourcing/jobs", "/v1/enrichment/status", "/v1/enrichment/runs"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert client.get(f"/v1/founders/{fid}").json()["enrichment_policy"] == "MANUAL"
    assert client.get(f"/v1/founders/{fid}").json()["social_background_id"] is None
    assert client.get("/v1/sourcing/status").json()["scheduler_enabled"] is False
    assert_quiet(isolated)


def test_upload_preserves_parsed_text_without_ai(isolated):
    fid, oid = create_case(isolated)
    text = "Pitch text with revenue and customer claims. " * 240
    response = isolated.client.post(f"/v1/opportunities/{oid}/deck?founder_id={fid}",
        files={"file": ("deck.txt", text.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "saved"
    assert response.json()["task_id"] is None
    claims = isolated.client.get(f"/v1/opportunities/{oid}/diligence").json()
    assert "".join(c["claim"] for c in claims) == text
    assert all(c["confidence"] == 0 for c in claims)
    assert_quiet(isolated)


def test_csv_dry_run_and_commit_are_quiet_and_preserve_scores(isolated):
    row = {key: "" for key in REQUIRED_COLUMNS}
    row.update(record_id="MANUAL-1", founder_name="Imported founder", project_name="ManualCo",
               primary_source_url="https://example.test/source", funding_status="no_public_institutional_funding_found",
               founder_score="81", founder_score_rationale="Imported evidence", vision_product_score="50",
               vision_product_rationale="Product evidence", differentiation_score="40", differentiation_rationale="Wedge",
               traction_score="30", traction_rationale="Early", evaluation_version="associate_screen_v1")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=sorted(row)); writer.writeheader(); writer.writerow(row)
    for dry_run in (True, False):
        response = isolated.client.post(f"/v1/founders/import-csv?dry_run={str(dry_run).lower()}",
            files={"file": ("founders.csv", buffer.getvalue().encode(), "text/csv")})
        assert response.status_code == 200, response.text
        assert not response.json()["errors"], response.text
    with isolated.factory() as db:
        profile = db.query(db_models.FounderScreeningProfile).one()
        assert profile.founder_score == 81
        assert crud.get_founder(db, profile.founder_id).enrichment_policy == "MANUAL"
    assert_quiet(isolated)


def test_approval_with_social_links_is_quiet(isolated):
    with isolated.factory() as db:
        crud.create_pool_items(db, [FounderPoolItem(id="pool_manual", name="Approved founder", reason="Evidence",
            linkedin_url="https://linkedin.com/in/approved", github_url="https://github.com/approved")])
    response = isolated.client.post("/v1/founders/pool/pool_manual/approve")
    assert response.status_code == 200, response.text
    assert response.json()["founder"]["enrichment_policy"] == "MANUAL"
    assert response.json()["opportunity_id"]
    assert_quiet(isolated)


def test_seed_all_is_data_only(isolated):
    response = isolated.client.post("/v1/seed/all")
    assert response.status_code == 200, response.text
    assert response.json()["founders_created"]
    assert_quiet(isolated)


@pytest.mark.parametrize("task,args", [
    (founder_pool.dispatch_sourcing_jobs, ()), (enrichment_task.dispatch_enrichment_jobs, ()),
    (founder_pool.refresh_pool_task, ()), (estimation_task.run_estimate, ("legacy",)),
    (enrichment_task.enrich_founder_chain, ("legacy",)),
    (document_extraction.extract_document, ("aGVsbG8=", "deck.txt", "legacy")),
    (social_research.research_social_background, ("legacy", "Name", "x@example.test", None, None)),
    (enrichment_task.enrich_social, ("legacy",)), (enrichment_task.enrich_deep_web, ("legacy",)),
    (enrichment_task.enrich_estimate, ("legacy",)), (founder_pool.refresh_founder_pool, ()),
])
def test_old_automatic_jobs_skip_before_any_access(monkeypatch, task, args):
    poison = Mock(side_effect=AssertionError("Legacy job touched external state"))
    monkeypatch.setattr(ai_policy, "_store", poison)
    for module in (founder_pool, enrichment_task, document_extraction, social_research):
        monkeypatch.setattr(module, "SessionLocal", poison)
    for _ in range(3):  # Replaying a dispatcher stays inert every time.
        result = task.run(*args) if hasattr(task, "run") else task(*args)
        assert result["status"] == "skipped_manual_required"
    poison.assert_not_called()


@pytest.mark.parametrize("workflow,path,task", [
    ("estimate", "estimate", estimation_task.run_estimate),
    ("enrich", "enrich", enrichment_task.enrich_founder_chain),
    ("social", "research-social", social_research.research_social_background),
])
def test_explicit_manual_request_queues_exactly_requested_task(isolated, workflow, path, task):
    fid, _ = create_case(isolated)
    response = isolated.client.post(f"/v1/founders/{fid}/{path}", json={"manual_intent": "client-forgery"})
    assert response.status_code == 200, response.text
    task.apply_async.assert_called_once()
    call = task.apply_async.call_args.kwargs
    assert response.json()["task_id"] == call["task_id"]
    intent = call["kwargs"]["manual_intent"]
    assert intent != "client-forgery"
    assert ai_policy.manual_allowed(intent, (workflow,), fid, call["task_id"])
    assert not ai_policy.manual_allowed(intent, ("source",), fid, call["task_id"])
    assert not ai_policy.manual_allowed(intent, (workflow,), "another-founder", call["task_id"])
    assert not ai_policy.manual_allowed(intent, (workflow,), fid, "another-task")
    assert sum(queue.call_count for queue in isolated.queues) == 1
    for provider in isolated.providers:
        provider.assert_not_called()


def test_manual_document_queues_only_extraction(isolated):
    fid, oid = create_case(isolated)
    response = isolated.client.post(f"/v1/opportunities/{oid}/deck/extract?founder_id={fid}",
        files={"file": ("deck.txt", b"Pitch", "text/plain")})
    assert response.status_code == 200, response.text
    document_extraction.extract_document.apply_async.assert_called_once()
    assert sum(q.call_count for q in isolated.queues) == 1


def test_manual_source_now_queues_only_sourcing(isolated):
    thesis = isolated.client.post("/v1/theses", json={"name": "Manual thesis"}).json()
    response = isolated.client.post(f"/v1/theses/{thesis['id']}/source-now")
    assert response.status_code == 200, response.text
    assert response.json()["job_id"]
    assert response.json()["task_id"]
    founder_pool.refresh_pool_task.apply_async.assert_called_once()
    assert sum(q.call_count for q in isolated.queues) == 1


def test_manual_estimate_executes_provider_only_with_matching_grant(isolated, monkeypatch):
    fid, _ = create_case(isolated)
    response = isolated.client.post(f"/v1/founders/{fid}/estimate")
    call = estimation_task.run_estimate.apply_async.call_args.kwargs
    provider = Mock(return_value={"founder_score": 61, "overall_confidence": 0.2})
    monkeypatch.setattr(estimation_task, "estimate_founder_scores", provider)
    estimation_task.run_estimate.push_request(id=call["task_id"])
    try:
        result = estimation_task.run_estimate.run(**call["kwargs"])
        assert result["status"] == "completed"
        provider.assert_called_once_with(fid)
        isolated.store.delete(f"manual-ai:grant:{call['kwargs']['manual_intent']}")
        assert estimation_task.run_estimate.run(**call["kwargs"])["status"] == "skipped_manual_required"
        assert provider.call_count == 1
    finally:
        estimation_task.run_estimate.pop_request()


def test_explicit_chain_requests_exact_three_stages(isolated, monkeypatch):
    fid, _ = create_case(isolated)
    isolated.client.post(f"/v1/founders/{fid}/enrich")
    call = enrichment_task.enrich_founder_chain.apply_async.call_args.kwargs
    stages = []
    for name in ("enrich_social", "enrich_deep_web", "enrich_estimate"):
        stage = Mock(return_value={"status": "completed"})
        monkeypatch.setattr(enrichment_task, name, stage)
        stages.append(stage)
    enrichment_task.enrich_founder_chain.push_request(id=call["task_id"])
    try:
        result = enrichment_task.enrich_founder_chain.run(**call["kwargs"])
        assert result["status"] == "completed"
        for stage in stages:
            stage.assert_called_once_with(fid, manual_intent=call["kwargs"]["manual_intent"], manual_task_id=call["task_id"])
        assert sum(q.call_count for q in isolated.queues) == 1
    finally:
        enrichment_task.enrich_founder_chain.pop_request()


def test_manual_endpoints_require_verified_owner(isolated):
    fid, _ = create_case(isolated)
    response = isolated.client.post(f"/v1/founders/{fid}/enrich", headers={"x-test-owner": "unverified"})
    assert response.status_code == 401
    assert_quiet(isolated)


def test_task_status_is_read_only_and_surfaces_failure(isolated, monkeypatch):
    fid, _ = create_case(isolated)
    queued = isolated.client.post(f"/v1/founders/{fid}/estimate").json()
    result = SimpleNamespace(state="STARTED", result=None)
    monkeypatch.setattr(celery, "AsyncResult", lambda task_id: result)
    path = f"/v1/ai/tasks/{queued['task_id']}"
    assert isolated.client.get(path).json()["status"] == "running"
    result.state = "FAILURE"
    response = isolated.client.get(path)
    assert response.json()["status"] == "failed"
    assert response.json()["error"]
    assert sum(q.call_count for q in isolated.queues) == 1


def test_scheduler_cannot_be_enabled(isolated):
    thesis = isolated.client.post("/v1/theses", json={"name": "No automatic jobs"}).json()
    schedule = isolated.client.post("/v1/sourcing/schedules", json={"thesis_id": thesis["id"], "enabled": True}).json()
    assert schedule["enabled"] is False
    response = isolated.client.put(f"/v1/sourcing/schedules/{schedule['id']}", json={"enabled": True})
    assert response.json()["enabled"] is False
    assert not celery.conf.beat_schedule
    assert_quiet(isolated)


def test_redis_credentials_never_logged(monkeypatch, caplog):
    import celery_app
    url = "redis://username:credential-test-secret@localhost:6379/0"
    monkeypatch.setenv("CELERY_BROKER_URL", url)
    monkeypatch.setenv("CELERY_RESULT_BACKEND", url)
    with caplog.at_level("INFO"):
        importlib.reload(celery_app)
    assert "celery_app.configured" in caplog.text
    assert "credential-test-secret" not in caplog.text
    assert "redis://" not in caplog.text


def run_queued(task):
    call = task.apply_async.call_args.kwargs
    task.push_request(id=call["task_id"])
    try:
        return task.run(**call["kwargs"])
    finally:
        task.pop_request()


def test_manual_sourcing_does_not_chain_social_or_estimates(isolated, monkeypatch):
    thesis = isolated.client.post("/v1/theses", json={"name": "Manual sourcing"}).json()
    isolated.client.post(f"/v1/theses/{thesis['id']}/source-now")
    agent = Mock()
    agent.discover.return_value = {"recommendations": [{"name": "Sourced manually", "reason": "A lead",
        "linkedin_url": "https://linkedin.com/in/manual-lead", "email": "lead@example.test"}]}
    monkeypatch.setattr(founder_pool, "SourcingAgent", Mock(return_value=agent))
    monkeypatch.setattr(founder_pool, "acquire_refresh_lock", lambda: True)
    monkeypatch.setattr(founder_pool, "release_refresh_lock", lambda: None)
    result = run_queued(founder_pool.refresh_pool_task)
    assert result["status"] == "completed"
    agent.discover.assert_called_once()
    with isolated.factory() as db:
        assert db.query(db_models.Founder).count() == 1
        assert db.query(db_models.Opportunity).count() == 1
        assert db.query(db_models.SocialMediaBackground).count() == 0
    assert sum(q.call_count for q in isolated.queues) == 1
    for provider in isolated.providers:
        provider.assert_not_called()


def test_manual_document_does_not_chain_estimation(isolated, monkeypatch):
    fid, oid = create_case(isolated)
    isolated.client.post(f"/v1/opportunities/{oid}/deck/extract?founder_id={fid}",
        files={"file": ("deck.txt", b"Pitch", "text/plain")})
    agent = Mock()
    agent.extract.return_value = {"claims": [{"claim": "A customer signed", "source": "Slide 2"}], "evidence": []}
    monkeypatch.setattr(document_extraction, "DocumentAgent", Mock(return_value=agent))
    result = run_queued(document_extraction.extract_document)
    assert result["status"] == "completed"
    assert result["claims_count"] == 1
    agent.extract.assert_called_once()
    assert sum(q.call_count for q in isolated.queues) == 1
    for provider in isolated.providers:
        provider.assert_not_called()


def test_manual_social_scores_deterministically_without_estimation(isolated, monkeypatch):
    fid, _ = create_case(isolated)
    isolated.client.post(f"/v1/founders/{fid}/research-social")
    agent = Mock()
    agent.research.return_value = {"summary": "Shipped software", "footprints": [], "evidence": [{
        "dimension": "execution_and_shipping", "observation": "Shipped a prototype",
        "source_type": "github", "source_locator": "https://github.com/manual", "evidence_type": "inspected_artifact",
        "rubric_level": 3, "source_trust": 0.8, "task_relevance": 0.9, "independence_group": "github",
        "recency_factor": 1.0, "polarity": "positive", "status": "positive"}]}
    monkeypatch.setattr(social_research, "SocialAgent", Mock(return_value=agent))
    result = run_queued(social_research.research_social_background)
    assert result["status"] == "completed"
    assert result["score_snapshot"]
    agent.research.assert_called_once()
    assert sum(q.call_count for q in isolated.queues) == 1
    for provider in isolated.providers:
        provider.assert_not_called()


def test_queue_failure_revokes_grant_and_records_failure(isolated):
    thesis = isolated.client.post("/v1/theses", json={"name": "Queue failure"}).json()
    founder_pool.refresh_pool_task.apply_async.side_effect = RuntimeError("Queue unavailable")
    response = isolated.client.post(f"/v1/theses/{thesis['id']}/source-now")
    assert response.status_code == 503
    assert not isolated.store.values
    with isolated.factory() as db:
        assert db.query(db_models.SourcingJob).one().status == "failed"


def test_expired_or_unavailable_grants_fail_closed(isolated, monkeypatch):
    fid, _ = create_case(isolated)
    isolated.client.post(f"/v1/founders/{fid}/estimate")
    call = estimation_task.run_estimate.apply_async.call_args.kwargs
    intent = call["kwargs"]["manual_intent"]
    key = f"manual-ai:grant:{intent}"
    grant = json.loads(isolated.store.get(key)); grant["expires_at"] = 0
    isolated.store.set(key, json.dumps(grant))
    assert not ai_policy.manual_allowed(intent, ("estimate",), fid, call["task_id"])
    monkeypatch.setattr(ai_policy, "_store", Mock(side_effect=RuntimeError("Unavailable")))
    assert not ai_policy.manual_allowed(intent, ("estimate",), fid, call["task_id"])
    for provider in isolated.providers:
        provider.assert_not_called()
