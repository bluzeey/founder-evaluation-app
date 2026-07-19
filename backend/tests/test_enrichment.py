from unittest.mock import patch

import crud
from models import Founder
from tasks.enrichment_task import (
    dispatch_enrichment_jobs,
    enrich_founder_chain,
    enrich_deep_web,
    enrich_estimate,
    enrich_social,
)


def _create_founder(db, founder_id="fnd_enr", linkedin_url=None, github_url=None):
    founder = Founder(
        id=founder_id,
        name="Enrich Test",
        email="enrich@example.com",
        current_company="TestCo",
        role="Founder",
        linkedin_url=linkedin_url,
        github_url=github_url,
        source_reason="Built and shipped an AI product end to end.",
    )
    return crud.create_founder(db, founder)


def _evidence_payload(stage="social"):
    return [
        {
            "dimension": "execution_and_shipping",
            "observation": f"{stage} shipped artifact",
            "source_type": "github",
            "source_locator": "https://example.com/x",
            "evidence_type": "inspected_artifact",
            "rubric_level": 3,
            "source_trust": 0.8,
            "task_relevance": 0.9,
            "recency_factor": 1.0,
            "independence_group": stage,
            "polarity": "positive",
            "status": "positive",
            "counter_evidence": None,
            "unknowns": None,
        }
    ]


def test_list_founders_below_confidence_targets_cold_start(db):
    _create_founder(db, "fnd_enr")
    candidates = crud.list_founders_below_confidence(
        db, threshold=0.30, max_results=10, min_gap_seconds=600
    )
    ids = [f.id for f in candidates]
    assert "fnd_enr" in ids


def test_enrich_social_skips_when_no_social_links(db):
    _create_founder(db, "fnd_no_social")
    result = enrich_social("fnd_no_social")
    assert result["status"] == "skipped"
    runs = crud.list_enrichment_runs(db, founder_id="fnd_no_social")
    assert len(runs) == 1
    assert runs[0].status == "skipped"


@patch("tasks.enrichment_task.research_social_background")
def test_enrich_social_runs_research_and_records_run(mock_social, db):
    _create_founder(db, "fnd_soc", linkedin_url="https://linkedin.com/in/x")
    mock_social.run.return_value = {"status": "completed", "score_snapshot": None}
    result = enrich_social("fnd_soc")
    assert result["status"] == "completed"
    runs = crud.list_enrichment_runs(db, founder_id="fnd_soc")
    assert len(runs) == 1
    assert runs[0].stage == "social"
    assert runs[0].status == "completed"


@patch("tasks.enrichment_task.OpenAIClient")
def test_enrich_deep_web_adds_evidence_and_scores(mock_client_cls, db):
    _create_founder(db, "fnd_web")
    mock_client = mock_client_cls.return_value
    mock_client.research.return_value = {
        "profile": {},
        "summary": "Public news coverage of shipping.",
        "sources": ["https://news.example.com/a"],
        "evidence": _evidence_payload(stage="news"),
    }
    result = enrich_deep_web("fnd_web")
    assert result["status"] == "completed"
    assert result["evidence_added"] == 1
    runs = crud.list_enrichment_runs(db, founder_id="fnd_web")
    assert runs[0].stage == "deep_web"
    assert runs[0].status == "completed"
    founder = crud.get_founder(db, "fnd_web")
    assert founder.ai_research_summary == "Public news coverage of shipping."


@patch("tasks.enrichment_task.estimate_founder_scores")
def test_enrich_estimate_records_run(mock_estimate, db):
    _create_founder(db, "fnd_est")
    mock_estimate.return_value = {"founder_score": 62, "overall_confidence": 0.35}
    result = enrich_estimate("fnd_est")
    assert result["status"] == "completed"
    runs = crud.list_enrichment_runs(db, founder_id="fnd_est")
    assert runs[0].stage == "estimate"
    assert runs[0].status == "completed"


@patch("tasks.enrichment_task.estimate_founder_scores")
@patch("tasks.enrichment_task.OpenAIClient")
@patch("tasks.enrichment_task.research_social_background")
def test_enrich_founder_chain_runs_all_three_stages(
    mock_social, mock_client_cls, mock_estimate, db
):
    _create_founder(db, "fnd_chain", linkedin_url="https://linkedin.com/in/y")
    mock_social.run.return_value = {"status": "completed"}
    mock_client_cls.return_value.research.return_value = {
        "profile": {},
        "summary": "News coverage.",
        "sources": ["https://news.example.com/b"],
        "evidence": _evidence_payload(stage="news"),
    }
    mock_estimate.return_value = {"founder_score": 64, "overall_confidence": 0.4}

    result = enrich_founder_chain.run("fnd_chain")
    stages = [r["stage"] for r in result["stages"]]
    assert "social" in stages
    assert "deep_web" in stages
    assert "estimate" in stages

    runs = crud.list_enrichment_runs(db, founder_id="fnd_chain")
    stage_names = {r.stage for r in runs}
    assert stage_names == {"social", "deep_web", "estimate"}

    founder = crud.get_founder(db, "fnd_chain")
    assert founder.last_enriched_at is not None
    assert founder.enrichment_attempts == 1


def test_dispatch_enrichment_jobs_queues_below_threshold(db):
    _create_founder(db, "fnd_disp")
    with patch("tasks.enrichment_task.enrich_founder_chain") as mock_chain:
        mock_chain.delay.return_value.id = "task_disp_1"
        result = dispatch_enrichment_jobs.run()

    assert result["dispatched"][0]["founder_id"] == "fnd_disp"
    founder = crud.get_founder(db, "fnd_disp")
    assert founder.last_enriched_at is not None


def test_enrichment_dispatcher_skips_already_enriched_founders(db):
    """Enrich-once: a founder that already has enrichment_attempts > 0 is not re-queued."""
    _create_founder(db, "fnd_done")
    crud.increment_enrichment_attempts(db, "fnd_done")
    with patch("tasks.enrichment_task.enrich_founder_chain") as mock_chain:
        result = dispatch_enrichment_jobs.run()

    assert result["dispatched"] == []
    mock_chain.delay.assert_not_called()


def test_dispatch_sourcing_skipped_when_founders_unenriched(db):
    """Automatic sourcing pauses while any below-threshold founder is unenriched."""
    _create_founder(db, "fnd_block")
    from tasks.founder_pool import dispatch_sourcing_jobs

    result = dispatch_sourcing_jobs.run()
    assert result.get("skipped_reason") == "enrichment_pending"
    assert result.get("below_threshold_unenriched") == 1
    assert result["dispatched"] == []


def test_dispatch_sourcing_resumes_after_enriched_once(db):
    """Once a founder has been enriched once it no longer blocks sourcing."""
    _create_founder(db, "fnd_unblock")
    crud.increment_enrichment_attempts(db, "fnd_unblock")  # mark as enriched once

    from tasks.founder_pool import dispatch_sourcing_jobs

    result = dispatch_sourcing_jobs.run()
    # No skip due to enrichment; with no due schedules, dispatched is empty.
    assert result.get("skipped_reason") != "enrichment_pending"
    assert result["dispatched"] == []
