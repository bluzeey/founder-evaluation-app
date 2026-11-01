import os
from unittest.mock import patch

import pytest
from manual_test_helpers import assert_queued_grant, local_task_delivery, manual_store
from tasks.founder_pool import refresh_pool_task

os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["OPENAI_API_KEY"] = "test-key"



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
    assert data["enabled"] is False

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
def test_source_now_creates_job(mock_agent_cls, client, thesis, manual_store):
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

    with local_task_delivery(refresh_pool_task) as send:
        r = client.post(f"/v1/theses/{thesis['id']}/source-now")
    assert r.status_code == 200
    data = r.json()
    assert data["thesis_id"] == thesis["id"]
    assert data["status"] == "queued"
    assert data["job_id"]
    assert_queued_grant(send, data, "source", thesis["id"])
    mock_agent.discover.assert_called_once()

    # The explicit API-issued task was delivered locally, without a broker.
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


def test_dispatch_sourcing_jobs_stays_inert_even_when_due(client, thesis):
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

    # Simulate an old enabled, overdue schedule retained from before manual mode.
    db = SessionLocal()
    crud.update_sourcing_schedule(
        db,
        schedule_id,
        {"enabled": True, "next_run_at": datetime.now(timezone.utc) - timedelta(minutes=1)},
    )
    db.close()

    with patch("tasks.founder_pool.SourcingAgent") as provider, \
         patch("tasks.founder_pool.refresh_pool_task") as refresh, \
         patch("tasks.founder_pool.SessionLocal") as session:
        for _ in range(3):
            result = dispatch_sourcing_jobs.run()
            assert result["status"] == "skipped_manual_required"
            assert result["dispatched"] == []
        provider.assert_not_called()
        refresh.delay.assert_not_called()
        refresh.apply_async.assert_not_called()
        session.assert_not_called()

    r = client.get("/v1/sourcing/jobs")
    assert r.status_code == 200
    assert r.json() == []
    with SessionLocal() as db:
        unchanged = crud.get_sourcing_schedule(db, schedule_id)
        assert unchanged.enabled is True
        assert unchanged.last_run_at is None
        assert unchanged.next_run_at < datetime.now(timezone.utc)


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
    assert data["scheduler_enabled"] is False
    assert data["ai_mode"] == "manual"
