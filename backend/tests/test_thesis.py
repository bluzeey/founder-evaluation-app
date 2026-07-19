import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def created_thesis(client: TestClient):
    payload = {
        "name": "Early-stage B2B SaaS",
        "sectors": ["B2B SaaS", "AI Infrastructure"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["India", "Europe"],
        "check_size_min": 250_000,
        "check_size_max": 1_500_000,
        "risk_appetite": "moderate",
    }
    response = client.post("/v1/theses", json=payload)
    assert response.status_code == 200
    return response.json()


def test_create_thesis(client: TestClient):
    payload = {
        "name": "Climate Tech",
        "sectors": ["Climate"],
        "stages": ["pre-seed"],
        "geographies": ["US"],
        "check_size_min": 100_000,
        "check_size_max": 500_000,
        "risk_appetite": "aggressive",
    }
    response = client.post("/v1/theses", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Climate Tech"
    assert data["sectors"] == ["Climate"]
    assert data["risk_appetite"] == "aggressive"
    assert data["id"].startswith("ths_")


def test_list_theses(client: TestClient, created_thesis):
    response = client.get("/v1/theses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == created_thesis["id"]


def test_get_thesis(client: TestClient, created_thesis):
    response = client.get(f"/v1/theses/{created_thesis['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_thesis["id"]
    assert data["name"] == created_thesis["name"]


def test_get_thesis_not_found(client: TestClient):
    response = client.get("/v1/theses/ths_nonexistent")
    assert response.status_code == 404


def test_update_thesis(client: TestClient, created_thesis):
    response = client.put(
        f"/v1/theses/{created_thesis['id']}",
        json={"name": "Updated name", "risk_appetite": "conservative"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated name"
    assert data["risk_appetite"] == "conservative"
    # Unchanged fields are preserved.
    assert data["sectors"] == created_thesis["sectors"]


def test_update_thesis_not_found(client: TestClient):
    response = client.put(
        "/v1/theses/ths_nonexistent",
        json={"name": "X"},
    )
    assert response.status_code == 404
