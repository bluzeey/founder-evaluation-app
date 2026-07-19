import pytest
from fastapi.testclient import TestClient


def test_seed_all_is_idempotent(client: TestClient):
    r1 = client.post("/v1/seed/all")
    assert r1.status_code == 200
    data1 = r1.json()
    assert len(data1["theses_created"]) == 5
    assert len(data1["schedules_created"]) == 5
    assert len(data1["founders_created"]) == 3
    assert len(data1["opportunities_created"]) == 3
    assert len(data1["pool_items_created"]) == 3

    r2 = client.post("/v1/seed/all")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["theses_created"] == []
    assert data2["schedules_created"] == []
    assert data2["founders_created"] == []
    assert data2["opportunities_created"] == []
    assert data2["pool_items_created"] == []

    # Schedules should have sources and a 1-hour interval.
    schedules = client.get("/v1/sourcing/schedules").json()
    assert len(schedules) == 5
    for s in schedules:
        assert s["interval_seconds"] == 3600
        assert len(s["sources"]) == 2
        assert s["sources"][0]["platform"] == "linkedin"
        assert s["sources"][1]["platform"] == "twitter"

    # Pool items should have a source field.
    pool = client.get("/v1/founders/pool").json()
    assert len(pool) == 3
    for item in pool:
        assert item["source"] in {"linkedin", "twitter"}

    # Opportunities should be created.
    opps = client.get("/v1/opportunities").json()
    assert len(opps) == 3
