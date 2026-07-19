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


def _create_opportunity(client: TestClient, opp_id: str) -> str:
    founder = client.post(
        "/v1/founders",
        json={"name": f"Founder {opp_id}", "email": f"{opp_id}@test.example"},
    ).json()
    client.post(f"/v1/opportunities/{opp_id}/screen?founder_id={founder['id']}")
    return founder["id"]


def test_opportunity_defaults_to_screening(client: TestClient):
    _create_opportunity(client, "opp_status_default")
    r = client.get("/v1/opportunities/opp_status_default")
    assert r.status_code == 200
    assert r.json()["status"] == "SCREENING"


def test_update_opportunity_status(client: TestClient):
    _create_opportunity(client, "opp_status_update")
    r = client.patch(
        "/v1/opportunities/opp_status_update/status",
        json={"status": "PARTNER_REVIEW"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PARTNER_REVIEW"

    r = client.get("/v1/opportunities/opp_status_update")
    assert r.json()["status"] == "PARTNER_REVIEW"


def test_update_opportunity_status_invalid(client: TestClient):
    _create_opportunity(client, "opp_status_invalid")
    r = client.patch(
        "/v1/opportunities/opp_status_invalid/status",
        json={"status": "NOT_A_STATUS"},
    )
    assert r.status_code == 400


def test_update_opportunity_status_not_found(client: TestClient):
    r = client.patch(
        "/v1/opportunities/opp_missing/status",
        json={"status": "PARTNER_REVIEW"},
    )
    assert r.status_code == 404


def test_screen_preserves_status(client: TestClient):
    _create_opportunity(client, "opp_preserve")
    client.patch(
        "/v1/opportunities/opp_preserve/status",
        json={"status": "PARTNER_REVIEW"},
    )
    r = client.post("/v1/opportunities/opp_preserve/screen")
    assert r.status_code == 200
    assert r.json()["status"] == "PARTNER_REVIEW"


def test_list_opportunities_status_filter(client: TestClient):
    _create_opportunity(client, "opp_filter_a")
    _create_opportunity(client, "opp_filter_b")
    client.patch(
        "/v1/opportunities/opp_filter_b/status",
        json={"status": "PARTNER_REVIEW"},
    )

    r = client.get("/v1/opportunities?status=PARTNER_REVIEW")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["opportunity_id"] == "opp_filter_b"

    r = client.get("/v1/opportunities?status=SCREENING")
    assert len(r.json()) == 1
    assert r.json()[0]["opportunity_id"] == "opp_filter_a"
