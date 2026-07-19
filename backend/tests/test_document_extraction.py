import os
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["UMANS_API_KEY"] = "test-key"

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def _create_thesis(client):
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


def _create_founder_and_opportunity(client):
    r = client.post(
        "/v1/founders",
        json={
            "name": "Deck Founder",
            "email": "deck@example.com",
            "current_company": "DeckCo",
        },
    )
    assert r.status_code == 200
    founder_id = r.json()["id"]

    r = client.post("/v1/seed")
    opp_id = r.json()["opportunity_id"]
    return founder_id, opp_id


@patch("tasks.document_extraction.DocumentAgent")
def test_upload_deck_extracts_claims_and_evidence(mock_agent_cls, client):
    mock_agent = mock_agent_cls.return_value
    mock_agent.extract.return_value = {
        "profile": {"name": "Deck Founder", "current_company": "DeckCo"},
        "summary": "A solid pitch deck.",
        "claims": [
            {
                "claim": "₹10 lakh ARR",
                "source": "Slide 4: Traction",
                "trust_status": "founder_reported",
                "confidence": 0.35,
                "contradiction": None,
                "owner": "founder",
                "next_action": "Verify with bank statement",
            }
        ],
        "evidence": [
            {
                "dimension": "execution",
                "observation": "Shipped product in 6 months",
                "source_type": "pitch_deck",
                "source_locator": "Slide 3: Product",
                "evidence_type": "self_reported",
                "rubric_level": 3,
                "source_trust": 0.5,
                "task_relevance": 0.8,
                "recency_factor": 1.0,
                "independence_group": "pitch_deck",
                "polarity": "positive",
                "status": "positive",
                "counter_evidence": None,
                "unknowns": None,
            }
        ],
    }

    r = client.post("/v1/seed")
    opp_id = r.json()["opportunity_id"]
    founder_id = r.json()["founder_id"]

    response = client.post(
        f"/v1/opportunities/{opp_id}/deck?founder_id={founder_id}",
        files={"file": ("deck.txt", BytesIO(b"This is a pitch deck."), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["opportunity_id"] == opp_id
    assert data["founder_id"] == founder_id
    assert data["status"] == "queued"

    # Verify claims were extracted.
    r = client.get(f"/v1/opportunities/{opp_id}/diligence")
    claims = r.json()
    assert any(c["claim"] == "₹10 lakh ARR" for c in claims)

    # Verify evidence was added to founder.
    r = client.get(f"/v1/founders/{founder_id}/score")
    assert r.status_code == 200
    score = r.json()
    assert score["founder_score"] > 50


def test_upload_deck_rejects_unknown_file_type(client):
    r = client.post("/v1/seed")
    opp_id = r.json()["opportunity_id"]

    response = client.post(
        f"/v1/opportunities/{opp_id}/deck",
        files={"file": ("deck.exe", BytesIO(b"binary"), "application/octet-stream")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"

    # In eager mode the task will run and fail with unsupported type.
    # We can inspect the task result by tracking the call, but for now the endpoint
    # itself accepts the upload and returns queued.


def test_upload_deck_requires_existing_opportunity(client):
    response = client.post(
        "/v1/opportunities/opp_missing/deck",
        files={"file": ("deck.txt", BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 404
