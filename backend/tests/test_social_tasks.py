import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

os.environ["CELERY_ALWAYS_EAGER"] = "true"

from tasks.social_research import (
    load_social_background,
    research_social_background,
    store_social_background,
)
from models import SocialMediaBackground


def test_store_and_load_social_background():
    bg = SocialMediaBackground(
        id="soc_test",
        founder_id="fnd_test",
        status="completed",
        summary="Test summary",
        footprints=[],
        evidence_items=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    store_social_background(bg)
    loaded = load_social_background("fnd_test")
    assert loaded is not None
    assert loaded.summary == "Test summary"


@patch("tasks.social_research.SocialAgent")
def test_research_social_background_task_runs_and_scores(mock_agent_cls):
    from research.extractor import evidence_from_llm

    mock_agent = mock_agent_cls.return_value
    mock_agent.research.return_value = {
        "summary": "Shipped code and shared learnings.",
        "footprints": [
            {"platform": "github", "url": "https://github.com/janedoe/x", "source_trust": 0.8}
        ],
        "evidence": [
            {
                "dimension": "execution",
                "observation": "Shipped project x",
                "source_type": "github",
                "source_locator": "https://github.com/janedoe/x",
                "evidence_type": "inspected_artifact",
                "rubric_level": 3,
                "source_trust": 0.8,
                "task_relevance": 0.9,
                "recency_factor": 1.0,
                "independence_group": "github",
                "polarity": "positive",
                "status": "positive",
                "counter_evidence": None,
                "unknowns": None,
            }
        ],
    }

    result = research_social_background.run(
        founder_id="fnd_test",
        name="Jane Doe",
        email="jane@example.com",
        linkedin_url=None,
        github_url="https://github.com/janedoe",
        auto_score=True,
    )

    assert result["status"] == "completed"
    assert result["score_snapshot"] is not None
    assert result["score_snapshot"]["founder_score"] > 0
    loaded = load_social_background("fnd_test")
    assert loaded.status == "completed"
