from unittest.mock import patch

from manual_test_helpers import assert_queued_grant, manual_store, queued_task_result


@patch("main.research_social_background")
def test_create_founder_does_not_queue_social_research(mock_task, client):
    response = client.post("/v1/founders", json={
        "name": "Jane Doe", "email": "jane@example.com", "current_company": "Acme Inc",
        "linkedin_url": "https://linkedin.com/in/janedoe", "github_url": "https://github.com/janedoe",
        "auto_score": True, "enrichment_policy": "AUTO",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["linkedin_url"] == "https://linkedin.com/in/janedoe"
    assert data["github_url"] == "https://github.com/janedoe"
    assert data["social_background_id"] is None
    assert data["enrichment_policy"] == "MANUAL"
    mock_task.delay.assert_not_called()
    mock_task.apply_async.assert_not_called()


@patch("tasks.social_research.SocialAgent")
def test_get_social_background_is_empty_until_manual_request(mock_agent_cls, client):
    response = client.post("/v1/founders", json={"name": "John Doe", "email": "john@example.com"})
    assert response.status_code == 200
    founder_id = response.json()["id"]
    response = client.get(f"/v1/founders/{founder_id}/social-background")
    assert response.status_code == 404
    mock_agent_cls.assert_not_called()


@patch("main.research_social_background.apply_async", side_effect=queued_task_result)
def test_manual_research_social_endpoint(mock_send, client, manual_store):
    response = client.post("/v1/founders", json={"name": "John Doe", "email": "john@example.com"})
    assert response.status_code == 200
    founder_id = response.json()["id"]
    response = client.post(f"/v1/founders/{founder_id}/research-social")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    call = assert_queued_grant(mock_send, data, "social", founder_id)
    assert call["kwargs"]["founder_id"] == founder_id
    background = client.get(f"/v1/founders/{founder_id}/social-background")
    assert background.status_code == 200
    assert background.json()["status"] == "pending"
