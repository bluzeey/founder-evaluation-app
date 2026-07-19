import pytest
from fastapi.testclient import TestClient


def test_list_opportunities_empty(client: TestClient):
    r = client.get("/v1/opportunities")
    assert r.status_code == 200
    assert r.json() == []


def test_get_opportunity_not_found(client: TestClient):
    r = client.get("/v1/opportunities/opp_missing")
    assert r.status_code == 404


def test_list_and_get_opportunity(client: TestClient):
    founder = client.post(
        "/v1/founders",
        json={
            "name": "Ava Test",
            "email": "ava@test.example",
            "current_company": "TestCo",
        },
    ).json()

    opp_id = "opp_test_001"
    screen = client.post(f"/v1/opportunities/{opp_id}/screen?founder_id={founder['id']}").json()
    assert screen["opportunity_id"] == opp_id
    assert screen["founder_id"] == founder["id"]

    r = client.get("/v1/opportunities")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["opportunity_id"] == opp_id

    r = client.get(f"/v1/opportunities/{opp_id}")
    assert r.status_code == 200
    assert r.json()["opportunity_id"] == opp_id
    assert r.json()["founder_id"] == founder["id"]


def test_screen_opportunity_uses_existing_record(client: TestClient):
    founder = client.post(
        "/v1/founders",
        json={"name": "Ben Test", "email": "ben@test.example"},
    ).json()

    opp_id = "opp_test_002"
    client.post(f"/v1/opportunities/{opp_id}/screen?founder_id={founder['id']}")

    # Re-screening an existing opportunity should return the stored record with updated score.
    r = client.post(f"/v1/opportunities/{opp_id}/screen")
    assert r.status_code == 200
    assert r.json()["opportunity_id"] == opp_id
