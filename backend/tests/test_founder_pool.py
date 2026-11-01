import os
from unittest.mock import patch

import pytest

os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["OPENAI_API_KEY"] = "test-key"

from models import FounderPoolItem, PoolItemStatus
from research.sourcing_agent import SourcingAgent
from tasks.founder_pool import load_founder_pool, refresh_founder_pool, save_founder_pool
from manual_test_helpers import assert_queued_grant, manual_store, queued_task_result


def test_save_and_load_pool():
    pool = [
        FounderPoolItem(
            id="pool_1",
            name="Jane Doe",
            current_company="Acme",
            reason="Shipped open-source tool",
            status=PoolItemStatus.RECOMMENDED,
        )
    ]
    save_founder_pool(pool)
    loaded = load_founder_pool()
    assert len(loaded) == 1
    assert loaded[0].name == "Jane Doe"


@patch("tasks.founder_pool.SourcingAgent")
def test_refresh_pool_adds_recommendations(mock_agent_cls, manual_store):
    mock_agent = mock_agent_cls.return_value
    mock_agent.discover.return_value = {
        "recommendations": [
            {
                "name": "Alice Smith",
                "current_company": "BetaCo",
                "role": "CEO",
                "location": "Bangalore",
                "source_url": "https://example.com/alice",
                "reason": "Built AI infra tool with early traction",
            }
        ]
    }
    run = manual_store.issue("source", "pool")
    pool = refresh_founder_pool(**run.stage_kwargs)
    assert len(pool) == 1
    assert pool[0].name == "Alice Smith"
    assert pool[0].status == PoolItemStatus.RECOMMENDED
    mock_agent.discover.assert_called_once()
    assert mock_agent.discover.call_args.kwargs["geographies"] == ["United States"]


@patch("main.refresh_pool_task.apply_async", side_effect=queued_task_result)
def test_refresh_pool_endpoint_queues_task(mock_task, client, manual_store):
    response = client.post("/v1/founders/pool/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert_queued_grant(mock_task, data, "source", "pool")


@patch("tasks.founder_pool.SourcingAgent")
def test_approve_pool_item_creates_founder(mock_agent_cls, client, manual_store):
    mock_agent = mock_agent_cls.return_value
    mock_agent.discover.return_value = {
        "recommendations": [
            {
                "name": "Bob Builder",
                "current_company": "Builder Inc",
                "role": "Founder",
                "linkedin_url": "https://linkedin.com/in/bob",
                "source_url": "https://example.com/bob",
                "reason": "Interesting",
            }
        ]
    }
    run = manual_store.issue("source", "pool")
    refresh_founder_pool(**run.stage_kwargs)
    pool = load_founder_pool()
    item_id = pool[0].id

    with patch("tasks.social_research.research_social_background.apply_async") as social, \
         patch("tasks.estimation_task.run_estimate.apply_async") as estimate:
        response = client.post(f"/v1/founders/pool/{item_id}/approve")
    social.assert_not_called()
    estimate.assert_not_called()
    assert response.status_code == 200
    data = response.json()
    assert data["founder"]["name"] == "Bob Builder"
    assert data["founder"]["linkedin_url"] == "https://linkedin.com/in/bob"
    assert data["opportunity_id"]
    assert data["founder"]["enrichment_policy"] == "MANUAL"
    assert data["founder"]["social_background_id"] is None

    updated = load_founder_pool()
    assert updated[0].status == PoolItemStatus.APPROVED


def test_dismiss_pool_item(client):
    save_founder_pool(
        [
            FounderPoolItem(
                id="pool_dismiss",
                name="Cara",
                reason="Test",
                status=PoolItemStatus.RECOMMENDED,
            )
        ]
    )
    response = client.post("/v1/founders/pool/pool_dismiss/dismiss")
    assert response.status_code == 200
    updated = load_founder_pool()
    assert updated[0].status == PoolItemStatus.DISMISSED


def test_list_pool_endpoint(client):
    save_founder_pool(
        [
            FounderPoolItem(
                id="pool_list",
                name="Dan",
                reason="Test",
                status=PoolItemStatus.RECOMMENDED,
            )
        ]
    )
    response = client.get("/v1/founders/pool")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Dan"


@patch("tasks.founder_pool.SourcingAgent")
def test_refresh_pool_skips_duplicates(mock_agent_cls, manual_store):
    save_founder_pool(
        [
            FounderPoolItem(
                id="pool_existing",
                name="Alice Smith",
                current_company="BetaCo",
                reason="Existing",
                status=PoolItemStatus.RECOMMENDED,
            )
        ]
    )
    mock_agent = mock_agent_cls.return_value
    mock_agent.discover.return_value = {
        "recommendations": [
            {
                "name": "Alice Smith",
                "current_company": "BetaCo",
                "source_url": "https://example.com/alice",
                "reason": "Built AI infra tool with early traction",
            }
        ]
    }
    run = manual_store.issue("source", "pool")
    pool = refresh_founder_pool(**run.stage_kwargs)
    assert len(pool) == 1
    assert pool[0].id == "pool_existing"


def test_sourcing_agent_validates_recommendations():
    agent = SourcingAgent(api_key="test-key")

    with pytest.raises(ValueError):
        agent._validate_recommendations({})

    with pytest.raises(ValueError):
        agent._validate_recommendations({"recommendations": []})

    with pytest.raises(ValueError):
        agent._validate_recommendations({"recommendations": [{"name": "No URL"}]})

    agent._validate_recommendations(
        {
            "recommendations": [
                {"name": "Valid", "source_url": "https://example.com/valid"}
            ]
        }
    )
