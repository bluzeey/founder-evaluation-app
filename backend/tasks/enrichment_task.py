import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from celery_app import app
from database import SessionLocal
import crud
from models import EnrichmentRun
from estimation import estimate_founder_scores
from research import OpenAIClient
from research.extractor import evidence_from_llm
from tasks.social_research import research_social_background

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config (env-driven, with sensible defaults)
# ---------------------------------------------------------------------------

ENRICHMENT_CONFIDENCE_THRESHOLD = float(
    os.environ.get("ENRICHMENT_CONFIDENCE_THRESHOLD", "0.30")
)
ENRICHMENT_MAX_FOUNDERS_PER_RUN = int(
    os.environ.get("ENRICHMENT_MAX_FOUNDERS_PER_RUN", "5")
)
ENRICHMENT_MIN_GAP_SECONDS = int(
    os.environ.get("ENRICHMENT_MIN_GAP_SECONDS", "600")
)


def _current_confidence(db, founder_id: str) -> float:
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder or not db_founder.latest_score_snapshot_id:
        return 0.0
    db_snapshot = crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id)
    if not db_snapshot:
        return 0.0
    return float(db_snapshot.overall_confidence)


def _start_run(db, founder_id: str, stage: str) -> EnrichmentRun:
    run = EnrichmentRun(
        id=f"enr_{uuid.uuid4().hex[:8]}",
        founder_id=founder_id,
        stage=stage,
        status="running",
        confidence_before=_current_confidence(db, founder_id),
        started_at=datetime.now(timezone.utc),
    )
    return crud.enrichment_run_to_pydantic(crud.create_enrichment_run(db, run))


# ---------------------------------------------------------------------------
# Stage 1: social background research (LinkedIn / GitHub)
# ---------------------------------------------------------------------------

def enrich_social(founder_id: str) -> Dict[str, Any]:
    """Re-run social background research for a founder and re-score."""
    db = SessionLocal()
    try:
        db_founder = crud.get_founder(db, founder_id)
        if not db_founder:
            return {"founder_id": founder_id, "stage": "social", "status": "skipped", "reason": "not_found"}

        if not (db_founder.linkedin_url or db_founder.github_url):
            run = _start_run(db, founder_id, "social")
            crud.update_enrichment_run(
                db,
                run.id,
                {
                    "status": "skipped",
                    "ended_at": datetime.now(timezone.utc),
                    "confidence_after": _current_confidence(db, founder_id),
                },
            )
            return {"founder_id": founder_id, "stage": "social", "status": "skipped", "reason": "no_social_links"}

        run = _start_run(db, founder_id, "social")
        run_id = run.id
        confidence_before = run.confidence_before or 0.0
    finally:
        db.close()

    # Run the existing social research task body synchronously so the chain
    # stays sequential. It opens its own session, stores the background, and
    # re-scores the founder when evidence is produced.
    try:
        db = SessionLocal()
        f = crud.get_founder(db, founder_id)
        name = f.name if f else ""
        email = f.email if f else ""
        linkedin_url = f.linkedin_url if f else None
        github_url = f.github_url if f else None
        db.close()
        research_social_background.run(
            founder_id=founder_id,
            name=name,
            email=email,
            linkedin_url=linkedin_url,
            github_url=github_url,
            auto_score=True,
        )
    except Exception as exc:
        logger.error("enrichment.social.failed founder_id=%s error=%s", founder_id, exc)
        db = SessionLocal()
        crud.update_enrichment_run(
            db,
            run_id,
            {
                "status": "failed",
                "ended_at": datetime.now(timezone.utc),
                "error_message": str(exc),
                "confidence_after": _current_confidence(db, founder_id),
            },
        )
        db.close()
        return {"founder_id": founder_id, "stage": "social", "status": "failed", "error": str(exc)}

    db = SessionLocal()
    confidence_after = _current_confidence(db, founder_id)
    # Count new evidence items added since the run started.
    evidence_count = len(crud.list_evidence_for_founder(db, founder_id))
    db.close()

    db = SessionLocal()
    crud.update_enrichment_run(
        db,
        run_id,
        {
            "status": "completed",
            "ended_at": datetime.now(timezone.utc),
            "confidence_after": confidence_after,
        },
    )
    db.close()
    logger.info(
        "enrichment.social.done founder_id=%s confidence %s->%s",
        founder_id,
        confidence_before,
        confidence_after,
    )
    return {"founder_id": founder_id, "stage": "social", "status": "completed", "confidence_after": confidence_after}


# ---------------------------------------------------------------------------
# Stage 2: deep web research (news, company blog, twitter)
# ---------------------------------------------------------------------------

def enrich_deep_web(founder_id: str) -> Dict[str, Any]:
    """Run OpenAI web research across news/company_blog/twitter and re-score."""
    db = SessionLocal()
    try:
        db_founder = crud.get_founder(db, founder_id)
        if not db_founder:
            return {"founder_id": founder_id, "stage": "deep_web", "status": "skipped", "reason": "not_found"}

        confidence_before = _current_confidence(db, founder_id)
        if confidence_before >= ENRICHMENT_CONFIDENCE_THRESHOLD:
            run = _start_run(db, founder_id, "deep_web")
            crud.update_enrichment_run(
                db,
                run.id,
                {
                    "status": "skipped",
                    "ended_at": datetime.now(timezone.utc),
                    "confidence_after": confidence_before,
                },
            )
            return {"founder_id": founder_id, "stage": "deep_web", "status": "skipped", "reason": "threshold_met"}

        run = _start_run(db, founder_id, "deep_web")
        run_id = run.id
        query = " ".join(
            part for part in [
                db_founder.name,
                db_founder.current_company,
                db_founder.role,
            ] if part
        ) or db_founder.name
    finally:
        db.close()

    try:
        client = OpenAIClient()
        result = client.research(query, ["news", "company_blog", "twitter"])
    except Exception as exc:
        logger.error("enrichment.deep_web.failed founder_id=%s error=%s", founder_id, exc)
        db = SessionLocal()
        crud.update_enrichment_run(
            db,
            run_id,
            {
                "status": "failed",
                "ended_at": datetime.now(timezone.utc),
                "error_message": str(exc),
                "confidence_after": _current_confidence(db, founder_id),
            },
        )
        db.close()
        return {"founder_id": founder_id, "stage": "deep_web", "status": "failed", "error": str(exc)}

    summary = result.get("summary", "") or ""
    sources = result.get("sources", []) or []
    raw_evidence = result.get("evidence", []) or []
    evidence_items = [evidence_from_llm(founder_id, item) for item in raw_evidence]

    db = SessionLocal()
    try:
        updates: Dict[str, Any] = {}
        if summary:
            updates["ai_research_summary"] = summary
        if sources:
            existing_sources = list(crud.get_founder(db, founder_id).ai_research_sources or [])
            updates["ai_research_sources"] = list(dict.fromkeys(existing_sources + sources))
        if updates:
            crud.update_founder(db, founder_id, updates)

        added = 0
        if evidence_items:
            crud.add_evidence_items(db, founder_id, evidence_items)
            added = len(evidence_items)
            all_items = crud.list_evidence_for_founder(db, founder_id)
            db_founder = crud.get_founder(db, founder_id)
            previous = (
                crud.score_snapshot_to_pydantic(snap)
                if db_founder.latest_score_snapshot_id
                and (snap := crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id))
                else None
            )
            from scoring import calculate_founder_score
            snapshot = calculate_founder_score(founder_id, all_items, previous)
            db_snapshot = crud.create_score_snapshot(db, snapshot)
            crud.update_founder(db, founder_id, {"latest_score_snapshot_id": db_snapshot.id})
            # Keep opportunity scores in sync.
            for db_opp in crud.list_opportunities(db, founder_id):
                db_opp.founder_score = snapshot.founder_score
                db_opp.founder_confidence = snapshot.overall_confidence
            db.commit()

        confidence_after = _current_confidence(db, founder_id)
        crud.update_enrichment_run(
            db,
            run_id,
            {
                "status": "completed",
                "evidence_added": added,
                "ended_at": datetime.now(timezone.utc),
                "confidence_after": confidence_after,
            },
        )
        logger.info(
            "enrichment.deep_web.done founder_id=%s evidence=%s confidence %s->%s",
            founder_id,
            added,
            confidence_before,
            confidence_after,
        )
        return {"founder_id": founder_id, "stage": "deep_web", "status": "completed", "evidence_added": added, "confidence_after": confidence_after}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stage 3: AI estimation (derive evidence per dimension from all context)
# ---------------------------------------------------------------------------

def enrich_estimate(founder_id: str) -> Dict[str, Any]:
    """Run AI estimation to fill any remaining unknown dimensions and re-score."""
    db = SessionLocal()
    try:
        db_founder = crud.get_founder(db, founder_id)
        if not db_founder:
            return {"founder_id": founder_id, "stage": "estimate", "status": "skipped", "reason": "not_found"}

        confidence_before = _current_confidence(db, founder_id)
        run = _start_run(db, founder_id, "estimate")
        run_id = run.id
    finally:
        db.close()

    try:
        result = estimate_founder_scores(founder_id)
    except Exception as exc:
        logger.error("enrichment.estimate.failed founder_id=%s error=%s", founder_id, exc)
        db = SessionLocal()
        crud.update_enrichment_run(
            db,
            run_id,
            {
                "status": "failed",
                "ended_at": datetime.now(timezone.utc),
                "error_message": str(exc),
                "confidence_after": _current_confidence(db, founder_id),
            },
        )
        db.close()
        return {"founder_id": founder_id, "stage": "estimate", "status": "failed", "error": str(exc)}

    confidence_after = (result or {}).get("overall_confidence") if isinstance(result, dict) else None
    db = SessionLocal()
    if confidence_after is None:
        confidence_after = _current_confidence(db, founder_id)
    evidence_count = len(crud.list_evidence_for_founder(db, founder_id))
    crud.update_enrichment_run(
        db,
        run_id,
        {
            "status": "completed" if result is not None else "skipped",
            "ended_at": datetime.now(timezone.utc),
            "confidence_after": confidence_after,
        },
    )
    db.close()
    logger.info(
        "enrichment.estimate.done founder_id=%s confidence %s->%s evidence=%s",
        founder_id,
        confidence_before,
        confidence_after,
        evidence_count,
    )
    return {"founder_id": founder_id, "stage": "estimate", "status": "completed" if result is not None else "skipped", "confidence_after": confidence_after}


# ---------------------------------------------------------------------------
# Chain task: runs all 3 stages sequentially with per-stage resilience
# ---------------------------------------------------------------------------

@app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    rate_limit="3/m",
)
def enrich_founder_chain(self, founder_id: str) -> Dict[str, Any]:
    """Run the full 3-stage enrichment pipeline for one founder.

    Stages run sequentially; a failure in one stage does not abort the others.
    Each stage records an EnrichmentRun row for observability. Stages
    short-circuit (status=skipped) once the founder crosses the confidence
    threshold.
    """
    logger.info("enrichment.chain.start founder_id=%s task_id=%s", founder_id, self.request.id)
    results = []
    for stage in (enrich_social, enrich_deep_web, enrich_estimate):
        try:
            res = stage(founder_id)
            results.append(res)
        except Exception as exc:
            logger.error("enrichment.chain.stage_error founder_id=%s stage=%s error=%s", founder_id, stage.__name__, exc)
            results.append({"founder_id": founder_id, "stage": stage.__name__, "status": "failed", "error": str(exc)})

    # Stamp last_enriched_at so the dispatcher debounces this founder, and
    # increment enrichment_attempts so the founder is no longer "never enriched".
    # This is what unblocks sourcing: a founder with enrichment_attempts > 0
    # stops counting toward the sourcing gate, even if confidence is still low.
    db = SessionLocal()
    try:
        crud.mark_founder_enriched(db, founder_id)
        crud.increment_enrichment_attempts(db, founder_id)
    finally:
        db.close()

    logger.info("enrichment.chain.end founder_id=%s results=%s", founder_id, results)
    return {"founder_id": founder_id, "stages": results}


# ---------------------------------------------------------------------------
# Dispatcher: recurring beat task that queues enrichment for weak founders
# ---------------------------------------------------------------------------

@app.task(bind=True, max_retries=2, default_retry_delay=30)
def dispatch_enrichment_jobs(self) -> Dict[str, Any]:
    """Celery beat task that finds founders below the confidence threshold and
    queues a 3-stage enrichment chain for each (debounced per founder).
    """
    now = datetime.now(timezone.utc)
    logger.info("enrichment.dispatch.start now=%s threshold=%s", now, ENRICHMENT_CONFIDENCE_THRESHOLD)

    db = SessionLocal()
    dispatched = []
    try:
        # Enrich-once semantics: only founders that have never completed an
        # enrichment pass (enrichment_attempts == 0) and are below the
        # confidence threshold are picked. Each founder is enriched exactly
        # once; after that it never re-enters the enrichment queue.
        candidates = crud.list_founders_below_confidence(
            db,
            threshold=ENRICHMENT_CONFIDENCE_THRESHOLD,
            max_results=ENRICHMENT_MAX_FOUNDERS_PER_RUN,
            min_gap_seconds=ENRICHMENT_MIN_GAP_SECONDS,
            never_enriched_only=True,
        )
        for db_founder in candidates:
            # Stamp last_enriched_at now so the founder isn't re-picked before
            # the gap elapses, even if the chain hasn't finished yet.
            crud.mark_founder_enriched(db, db_founder.id, enriched_at=now)
            task = enrich_founder_chain.delay(db_founder.id)
            dispatched.append({"founder_id": db_founder.id, "task_id": task.id})

        # Track last dispatch time in Redis for health checks (best-effort).
        try:
            import redis
            redis_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
            client = redis.from_url(redis_url, decode_responses=True)
            client.set("enrichment:last_dispatch_at", now.isoformat())
        except Exception as exc:
            logger.warning("enrichment.dispatch.redis_health_failed error=%s", exc)

        logger.info("enrichment.dispatch.end dispatched=%s", len(dispatched))
        return {"dispatched": dispatched, "now": now.isoformat()}
    except Exception as exc:
        logger.error("enrichment.dispatch.error error=%s", exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
