import os
from io import BytesIO
from unittest.mock import patch

from manual_test_helpers import assert_queued_grant, local_task_delivery, manual_store
from tasks.document_extraction import extract_document


os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["OPENAI_API_KEY"] = "test-key"



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

    opp_id = f"opp_{__import__('uuid').uuid4().hex[:8]}"
    r = client.post(f"/v1/opportunities/{opp_id}/screen?founder_id={founder_id}")
    assert r.status_code == 200
    return founder_id, opp_id


@patch("tasks.document_extraction.DocumentAgent")
def test_manual_deck_extraction_adds_claims_and_evidence(mock_agent_cls, client, manual_store):
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
                "dimension": "execution_and_shipping",
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

    founder_id, opp_id = _create_founder_and_opportunity(client)

    with local_task_delivery(extract_document) as send:
        response = client.post(
            f"/v1/opportunities/{opp_id}/deck/extract?founder_id={founder_id}",
            files={"file": ("deck.txt", BytesIO(b"This is a pitch deck."), "text/plain")},
        )
    assert response.status_code == 200
    assert_queued_grant(send, response.json(), "document", opp_id)
    mock_agent.extract.assert_called_once()
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
    _, opp_id = _create_founder_and_opportunity(client)

    response = client.post(
        f"/v1/opportunities/{opp_id}/deck",
        files={"file": ("deck.exe", BytesIO(b"binary"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Supported files" in response.json()["detail"]


def test_upload_deck_requires_existing_opportunity(client):
    response = client.post(
        "/v1/opportunities/opp_missing/deck",
        files={"file": ("deck.txt", BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 404


@patch("tasks.document_extraction.DocumentAgent")
@patch("main.extract_document.apply_async")
def test_ordinary_upload_preserves_text_without_ai(mock_send, mock_agent, client):
    founder_id, opp_id = _create_founder_and_opportunity(client)
    text = "Ordinary document text with founder claims."
    response = client.post(
        f"/v1/opportunities/{opp_id}/deck?founder_id={founder_id}",
        files={"file": ("deck.txt", BytesIO(text.encode()), "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert response.json()["task_id"] is None
    claims = client.get(f"/v1/opportunities/{opp_id}/diligence").json()
    assert [claim["claim"] for claim in claims] == [text]
    mock_send.assert_not_called()
    mock_agent.assert_not_called()
