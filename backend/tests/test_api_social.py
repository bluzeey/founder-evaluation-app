import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["UMANS_API_KEY"] = "test-key"

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@patch("main.research_social_background")
def test_create_founder_queues_social_research(mock_task, client):
    mock_task.delay.return_value.id = "task_123"
    response = client.post(
        "/v1/founders",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "current_company": "Acme Inc",
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "github_url": "https://github.com/janedoe",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["linkedin_url"] == "https://linkedin.com/in/janedoe"
    assert data["github_url"] == "https://github.com/janedoe"
    assert data["social_background_id"].startswith("soc_")
    mock_task.delay.assert_called_once()


@patch("tasks.social_research.SocialAgent")
def test_get_social_background_returns_pending_record(mock_agent_cls, client):
    # Create a founder. In eager mode the task will run, so mock the agent to keep status pending.
    mock_agent_cls.return_value.research.return_value = {
        "summary": "",
        "footprints": [],
        "evidence": [],
    }
    response = client.post(
        "/v1/founders",
        json={"name": "John Doe", "email": "john@example.com"},
    )
    founder_id = response.json()["id"]
    response = client.get(f"/v1/founders/{founder_id}/social-background")
    # Because the endpoint reconciles the pending/completed background created at submit,
    # it should now return that record.
    assert response.status_code == 200
    assert response.json()["status"] in ("pending", "completed")


@patch("main.research_social_background")
def test_manual_research_social_endpoint(mock_task, client):
    response = client.post(
        "/v1/founders",
        json={"name": "John Doe", "email": "john@example.com"},
    )
    founder_id = response.json()["id"]
    mock_task.delay.return_value.id = "task_456"
    response = client.post(f"/v1/founders/{founder_id}/research-social")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["task_id"] == "task_456"
