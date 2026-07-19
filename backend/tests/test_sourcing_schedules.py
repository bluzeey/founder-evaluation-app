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


@pytest.fixture
def thesis(client):
    r = client.post(
        "/v1/theses",
        json={
            "name": "AI SaaS",
            "sectors": ["AI", "B2B SaaS"],
            "stages": ["seed"],
            "geographies": ["India"],
        },
    )
    assert r.status_code == 200
    return r.json()


def test_create_and_list_sourcing_schedule(client, thesis):
    r = client.post(
        "/v1/sourcing/schedules",
        json={
            "thesis_id": thesis["id"],
            "enabled": True,
            "interval_seconds": 1800,
            "max_leads_per_run": 5,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["thesis_id"] == thesis["id"]
    assert data["interval_seconds"] == 1800
    assert data["enabled"] is True

    r = client.get("/v1/sourcing/schedules")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_duplicate_schedule_for_same_thesis_rejected(client, thesis):
    r = client.post(
        "/v1/sourcing/schedules",
        json={"thesis_id": thesis["id"], "interval_seconds": 3600},
    )
    assert r.status_code == 200

    r = client.post(
        "/v1/sourcing/schedules",
        json={"thesis_id": thesis["id"], "interval_seconds": 7200},
    )
    assert r.status_code == 400


def test_update_and_delete_sourcing_schedule(client, thesis):
    r = client.post(
        "/v1/sourcing/schedules",
        json={"thesis_id": thesis["id"], "interval_seconds": 3600},
    )
    schedule_id = r.json()["id"]

    r = client.put(
        f"/v1/sourcing/schedules/{schedule_id}",
        json={"enabled": False, "interval_seconds": 7200},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["interval_seconds"] == 7200

    r = client.delete(f"/v1/sourcing/schedules/{schedule_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    r = client.get(f"/v1/sourcing/schedules/{schedule_id}")
    assert r.status_code == 404


@patch("tasks.founder_pool.SourcingAgent")
def test_source_now_creates_job(mock_agent_cls, client, thesis):
    mock_agent = mock_agent_cls.return_value
    mock_agent.discover.return_value = {
        "recommendations": [
            {
                "name": "Sourced Founder",
                "current_company": "SourceCo",
                "source_url": "https://example.com/source",
                "reason": "Interesting",
            }
        ]
    }

    r = client.post(f"/v1/theses/{thesis['id']}/source-now")
    assert r.status_code == 200
    data = r.json()
    assert data["thesis_id"] == thesis["id"]
    assert data["status"] == "queued"
    assert data["job_id"]

    # Job should be listed and completed in eager mode.
    r = client.get("/v1/sourcing/jobs")
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["leads_added"] == 1

    # Pool should contain the new lead.
    r = client.get("/v1/founders/pool")
    pool = r.json()
    assert any(p["name"] == "Sourced Founder" for p in pool)


def test_dispatch_sourcing_jobs_respects_due_time(client, thesis):
    # Create a schedule with a far-future next_run_at so it is not due.
    r = client.post(
        "/v1/sourcing/schedules",
        json={"thesis_id": thesis["id"], "interval_seconds": 3600},
    )
    schedule_id = r.json()["id"]

    # Set next_run_at far in the future.
    from database import SessionLocal
    import crud
    from datetime import datetime, timezone, timedelta

    db = SessionLocal()
    crud.update_sourcing_schedule(
        db,
        schedule_id,
        {"next_run_at": datetime.now(timezone.utc) + timedelta(days=1)},
    )
    db.close()

    # Run dispatch manually.
    from tasks.founder_pool import dispatch_sourcing_jobs
    result = dispatch_sourcing_jobs.run()
    assert result["dispatched"] == []

    # Set next_run_at in the past.
    db = SessionLocal()
    crud.update_sourcing_schedule(
        db,
        schedule_id,
        {"next_run_at": datetime.now(timezone.utc) - timedelta(minutes=1)},
    )
    db.close()

    with patch("tasks.founder_pool.SourcingAgent") as mock_agent_cls:
        mock_agent = mock_agent_cls.return_value
        mock_agent.discover.return_value = {"recommendations": []}
        result = dispatch_sourcing_jobs.run()
        assert len(result["dispatched"]) == 1
        assert result["dispatched"][0]["thesis_id"] == thesis["id"]

    r = client.get("/v1/sourcing/jobs")
    assert len(r.json()) >= 1


def test_seed_creates_default_sourcing_schedule(client):
    r = client.post("/v1/seed")
    assert r.status_code == 200
    thesis_id = r.json()["thesis_id"]

    r = client.get("/v1/sourcing/schedules")
    assert r.status_code == 200
    schedules = r.json()
    assert any(s["thesis_id"] == thesis_id for s in schedules)


def test_sourcing_status_endpoint(client, thesis):
    r = client.post(
        "/v1/sourcing/schedules",
        json={"thesis_id": thesis["id"], "interval_seconds": 3600},
    )
    assert r.status_code == 200

    r = client.get("/v1/sourcing/status")
    assert r.status_code == 200
    data = r.json()
    assert "schedules" in data
    assert "active_jobs" in data
    assert "recent_jobs" in data
    assert len(data["schedules"]) >= 1
