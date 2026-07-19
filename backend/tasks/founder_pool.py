import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis

from celery_app import app
from database import SessionLocal
import crud
import db_models
from models import (
    Founder,
    FounderMarketFit,
    FounderPoolItem,
    OpportunityScreen,
    PoolItemStatus,
    SocialMediaBackground,
    SourcingJob,
    TeamCompleteness,
)
from research import SourcingAgent
from scoring import calculate_founder_score
from estimation import estimate_founder_scores
from tasks.retry_utils import SOURCING_MAX_RETRIES, SOURCING_RETRY_BASE_DELAY, maybe_retry
from tasks.social_research import research_social_background, store_social_background

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
POOL_LOCK_KEY = "founder_pool_refresh_lock"
POOL_LOCK_TTL_SECONDS = int(os.environ.get("POOL_LOCK_TTL_SECONDS", "300"))


def _redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def _dedup_key(item: FounderPoolItem) -> str:
    name = (item.name or "").lower().strip()
    company = (item.current_company or "").lower().strip()
    linkedin = (item.linkedin_url or "").lower().strip()
    return f"{name}|{company}|{linkedin}"


def load_founder_pool(status: Optional[str] = None) -> List[FounderPoolItem]:
    """Load the current founder pool from the database."""
    db = SessionLocal()
    try:
        db_items = crud.list_pool_items(db, status=status)
        return [crud.pool_item_to_pydantic(item) for item in db_items]
    finally:
        db.close()


def save_founder_pool(pool: List[FounderPoolItem]) -> None:
    """Persist the latest pool statuses to the database.

    Existing items are updated; new items are inserted.
    """
    db = SessionLocal()
    try:
        new_items = []
        for item in pool:
            db_item = crud.get_pool_item(db, item.id)
            if db_item:
                db_item.status = item.status.value
            else:
                new_items.append(item)
        if new_items:
            crud.create_pool_items(db, new_items)
        db.commit()
    finally:
        db.close()


def acquire_refresh_lock() -> bool:
    """Try to acquire a distributed lock so only one worker refreshes the pool."""
    if app.conf.task_always_eager:
        logger.info("founder_pool.refresh_lock.skip_always_eager")
        return True

    client = _redis_client()
    acquired = client.set(POOL_LOCK_KEY, "1", nx=True, ex=POOL_LOCK_TTL_SECONDS)
    if acquired:
        logger.info("founder_pool.refresh_lock.acquired ttl=%s", POOL_LOCK_TTL_SECONDS)
    else:
        logger.warning("founder_pool.refresh_lock.already_locked")
    return bool(acquired)


def release_refresh_lock() -> None:
    """Release the distributed refresh lock."""
    if app.conf.task_always_eager:
        return
    try:
        client = _redis_client()
        client.delete(POOL_LOCK_KEY)
        logger.info("founder_pool.refresh_lock.released")
    except Exception as exc:
        logger.warning("founder_pool.refresh_lock.release_failed error=%s", exc)


def _founder_exists(db, item: FounderPoolItem) -> bool:
    """Check whether a founder with the same dedup key already exists."""
    from sqlalchemy import func

    name_norm = (item.name or "").lower().strip()
    company_norm = (item.current_company or "").lower().strip()
    linkedin_norm = (item.linkedin_url or "").lower().strip()

    existing = (
        db.query(db_models.Founder)
        .filter(
            func.lower(func.trim(db_models.Founder.name)) == name_norm,
            func.lower(func.trim(db_models.Founder.current_company)) == company_norm,
            func.lower(func.trim(db_models.Founder.linkedin_url)) == linkedin_norm,
        )
        .first()
    )
    return existing is not None


def _matching_founder(db, item: FounderPoolItem) -> Optional[db_models.Founder]:
    """Return the existing founder that matches the pool item dedup key, if any."""
    from sqlalchemy import func

    name_norm = (item.name or "").lower().strip()
    company_norm = (item.current_company or "").lower().strip()
    linkedin_norm = (item.linkedin_url or "").lower().strip()
    return (
        db.query(db_models.Founder)
        .filter(
            func.lower(func.trim(db_models.Founder.name)) == name_norm,
            func.lower(func.trim(db_models.Founder.current_company)) == company_norm,
            func.lower(func.trim(db_models.Founder.linkedin_url)) == linkedin_norm,
        )
        .first()
    )


def create_founder_and_opportunity_from_pool_item(
    db, item: FounderPoolItem
) -> Tuple[Founder, Optional[str]]:
    """Promote a sourced pool item into a Founder + cold-start Opportunity.

    If a matching founder already exists, return the existing founder and
    opportunity (if one exists) without creating duplicates.
    """
    existing_db_founder = _matching_founder(db, item)
    if existing_db_founder:
        existing_founder = crud.founder_to_pydantic(db, existing_db_founder)
        existing_opps = crud.list_opportunities(db, founder_id=existing_founder.id)
        existing_opp_id = existing_opps[0].id if existing_opps else None
        return existing_founder, existing_opp_id

    founder_id = f"fnd_{uuid.uuid4().hex[:8]}"
    founder = Founder(
        id=founder_id,
        name=item.name,
        email=item.email or f"{item.name.lower().replace(' ', '.')}@example.com",
        current_company=item.current_company,
        role=item.role,
        location=item.location,
        linkedin_url=item.linkedin_url,
        github_url=item.github_url,
        source_reason=item.reason,
        source_url=item.source_url,
    )
    crud.create_founder(db, founder)

    # Cold-start score snapshot (score near neutral, low confidence, all unknowns).
    snapshot = calculate_founder_score(founder.id, [])
    db_snapshot = crud.create_score_snapshot(db, snapshot)
    crud.update_founder(db, founder.id, {"latest_score_snapshot_id": db_snapshot.id})

    # Create an opportunity so the founder has a case file to evaluate.
    opportunity_id = f"opp_{uuid.uuid4().hex[:8]}"
    opp = OpportunityScreen(
        opportunity_id=opportunity_id,
        founder_id=founder.id,
        founder_score=snapshot.founder_score,
        founder_confidence=snapshot.overall_confidence,
        founder_market_fit=FounderMarketFit(score=None, confidence=0.0, coverage=0.0),
        team_completeness=TeamCompleteness(score=None, confidence=0.0, coverage=0.0),
        market_posture="neutral",
        market_confidence=0.0,
        idea_vs_market_posture="neutral",
        idea_vs_market_confidence=0.0,
        next_founder_action="Run structured cold-start assessment.",
    )
    crud.create_or_update_opportunity(db, opp)

    # Auto-trigger social background research when links are available.
    if item.linkedin_url or item.github_url:
        background_id = f"soc_{uuid.uuid4().hex[:8]}"
        crud.update_founder(db, founder_id, {"social_background_id": background_id})
        pending = SocialMediaBackground(
            id=background_id,
            founder_id=founder_id,
            status="pending",
            linkedin_url=item.linkedin_url,
            github_url=item.github_url,
        )
        store_social_background(pending)
        research_social_background.delay(
            founder_id=founder_id,
            name=founder.name,
            email=founder.email,
            linkedin_url=item.linkedin_url,
            github_url=item.github_url,
            auto_score=True,
        )

    return crud.founder_to_pydantic(db, crud.get_founder(db, founder_id)), opportunity_id


def refresh_founder_pool(
    sectors: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    geographies: Optional[List[str]] = None,
    risk_appetite: str = "moderate",
    sources: Optional[List[dict[str, str]]] = None,
    thesis_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> List[FounderPoolItem]:
    """Run the sourcing agent and append new recommendations to the database pool.

    Existing recommended items are replaced; approved/dismissed items are preserved.
    Duplicate candidates are skipped against both the pool and existing founders.
    """
    sectors = sectors or ["B2B SaaS", "AI Infrastructure"]
    stages = stages or ["pre-seed", "seed"]
    geographies = geographies or ["Global"]

    logger.info(
        "founder_pool.refresh.start sectors=%s stages=%s geographies=%s risk=%s sources=%s thesis_id=%s job_id=%s",
        sectors,
        stages,
        geographies,
        risk_appetite,
        sources,
        thesis_id,
        job_id,
    )

    if not acquire_refresh_lock():
        logger.warning("founder_pool.refresh.skip_locked")
        return load_founder_pool()

    db = SessionLocal()
    try:
        # Mark job as running if provided.
        if job_id:
            crud.update_sourcing_job(
                db,
                job_id,
                {
                    "status": "searching",
                    "progress": 10,
                    "started_at": datetime.now(timezone.utc),
                },
            )

        existing = crud.list_pool_items(db)
        logger.info("founder_pool.refresh.existing_count count=%s", len(existing))

        agent = SourcingAgent()
        result = agent.discover(
            sectors=sectors,
            stages=stages,
            geographies=geographies,
            risk_appetite=risk_appetite,
            sources=sources,
        )

        recommendations = result.get("recommendations", []) or []

        if job_id:
            crud.update_sourcing_job(
                db,
                job_id,
                {
                    "status": "deduplicating",
                    "progress": 50,
                    "leads_found": len(recommendations),
                },
            )

        # Build a set of existing dedup keys across the whole pool.
        existing_keys = {_dedup_key(crud.pool_item_to_pydantic(item)) for item in existing}

        default_source = sources[0].get("platform", "web") if sources else "web"
        new_items = []
        skipped = 0
        for rec in recommendations:
            item = FounderPoolItem(
                id=f"pool_{uuid.uuid4().hex[:8]}",
                name=rec.get("name", "Unknown") or "Unknown",
                email=rec.get("email") or None,
                current_company=rec.get("current_company") or None,
                role=rec.get("role") or None,
                location=rec.get("location") or None,
                linkedin_url=rec.get("linkedin_url") or None,
                github_url=rec.get("github_url") or None,
                source_url=rec.get("source_url") or None,
                source=(rec.get("source") or default_source) if sources else None,
                reason=rec.get("reason", "") or "",
                thesis_id=thesis_id,
                job_id=job_id,
            )
            key = _dedup_key(item)
            if (
                key in existing_keys
                or crud.pool_item_exists(db, item.name, item.current_company, item.linkedin_url)
                or _founder_exists(db, item)
            ):
                skipped += 1
                logger.info(
                    "founder_pool.refresh.skip_duplicate name=%s company=%s",
                    item.name,
                    item.current_company,
                )
                continue
            existing_keys.add(key)
            new_items.append(item)

        # Replace existing recommended items with the new batch when we have
        # valid new candidates; otherwise keep the old recommendations so the
        # pool does not empty unexpectedly. Approved/dismissed items are kept.
        if job_id:
            crud.update_sourcing_job(
                db,
                job_id,
                {
                    "status": "persisting",
                    "progress": 80,
                },
            )

        if new_items:
            crud.create_pool_items(db, new_items)

            # Every sourced lead becomes a founder case with a cold-start score.
            # Social background research is queued automatically when links exist.
            for item in new_items:
                founder, _ = create_founder_and_opportunity_from_pool_item(db, item)
                # Estimate dimension scores from the source signal and any available context.
                estimate_founder_scores(founder.id, db=db)

            db.commit()

        final_pool = crud.list_pool_items(db)

        # Update job if provided.
        if job_id:
            crud.update_sourcing_job(
                db,
                job_id,
                {
                    "status": "completed",
                    "progress": 100,
                    "ended_at": datetime.now(timezone.utc),
                    "leads_found": len(recommendations),
                    "leads_added": len(new_items),
                    "leads_skipped": skipped,
                    "result": {
                        "recommendations": recommendations,
                        "added": [item.model_dump(mode="json") for item in new_items],
                    },
                },
            )

        logger.info(
            "founder_pool.refresh.end added=%s skipped=%s total=%s",
            len(new_items),
            skipped,
            len(final_pool),
        )
        return load_founder_pool()
    except Exception as exc:
        logger.error("founder_pool.refresh.error error=%s", exc)
        if job_id:
            crud.update_sourcing_job(
                db,
                job_id,
                {
                    "status": "failed",
                    "progress": 0,
                    "ended_at": datetime.now(timezone.utc),
                    "error_message": str(exc),
                },
            )
        raise
    finally:
        release_refresh_lock()
        db.close()


def run_sourcing_job(thesis_id: str) -> str:
    """Create a sourcing job record and dispatch the Celery task."""
    db = SessionLocal()
    try:
        db_thesis = crud.get_thesis(db, thesis_id)
        if not db_thesis:
            raise ValueError(f"Thesis not found: {thesis_id}")
        thesis = crud.thesis_to_pydantic(db_thesis)

        # Prefer the active schedule for this thesis to get sources and interval context.
        db_schedule = crud.get_sourcing_schedule_by_thesis(db, thesis_id)
        schedule = crud.sourcing_schedule_to_pydantic(db_schedule) if db_schedule else None

        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = SourcingJob(
            id=job_id,
            thesis_id=thesis_id,
            schedule_id=schedule.id if schedule else None,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        crud.create_sourcing_job(db, job)

        refresh_pool_task.delay(
            sectors=thesis.sectors,
            stages=thesis.stages,
            geographies=thesis.geographies,
            risk_appetite=thesis.risk_appetite,
            sources=[s.model_dump(mode="json") for s in schedule.sources] if schedule and schedule.sources else None,
            thesis_id=thesis_id,
            job_id=job_id,
        )
        return job_id
    finally:
        db.close()


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def dispatch_sourcing_jobs(self) -> Dict[str, Any]:
    """Celery beat task that dispatches sourcing jobs for due schedules.

    Gated on enrichment: automatic sourcing is paused while any founder is
    below the enrichment confidence threshold AND has not yet completed an
    enrichment pass. Once every founder has been enriched once, sourcing
    resumes. Manual sourcing endpoints (Refresh pool / Source now) are NOT
    gated and remain available as explicit overrides.
    """
    now = datetime.now(timezone.utc)
    logger.info("founder_pool.dispatch_sourcing_jobs.start now=%s", now)

    db = SessionLocal()
    dispatched = []
    try:
        # Enrichment gate: do not source new leads while existing founders are
        # still awaiting their one enrichment pass. Founders that have already
        # been enriched once (enrichment_attempts > 0) no longer block.
        enrichment_threshold = float(
            os.environ.get("ENRICHMENT_CONFIDENCE_THRESHOLD", "0.30")
        )
        blocking = crud.count_founders_blocking_sourcing(db, threshold=enrichment_threshold)
        if blocking > 0:
            logger.info(
                "founder_pool.dispatch_sourcing_jobs.skip_enrichment_pending below_threshold_unenriched=%s",
                blocking,
            )
            return {
                "dispatched": [],
                "skipped_reason": "enrichment_pending",
                "below_threshold_unenriched": blocking,
                "now": now.isoformat(),
            }

        due_schedules = crud.list_due_sourcing_schedules(db, now)
        for db_schedule in due_schedules:
            schedule = crud.sourcing_schedule_to_pydantic(db_schedule)

            # Skip if a job for this schedule is already running.
            running = (
                db.query(db_models.SourcingJob)
                .filter(
                    db_models.SourcingJob.schedule_id == schedule.id,
                    db_models.SourcingJob.status == "running",
                )
                .first()
            )
            if running:
                logger.info(
                    "founder_pool.dispatch_sourcing_jobs.skip_running schedule_id=%s",
                    schedule.id,
                )
                continue

            job_id = run_sourcing_job(schedule.thesis_id)
            next_run = now + timedelta(seconds=schedule.interval_seconds)
            crud.update_sourcing_schedule(
                db,
                schedule.id,
                {
                    "last_run_at": now,
                    "next_run_at": next_run,
                },
            )
            dispatched.append(
                {
                    "schedule_id": schedule.id,
                    "thesis_id": schedule.thesis_id,
                    "job_id": job_id,
                    "next_run_at": next_run.isoformat(),
                }
            )

        # Track the last successful dispatch time in Redis for health checks.
        try:
            client = _redis_client()
            client.set("sourcing:last_dispatch_at", now.isoformat())
        except Exception as exc:
            logger.warning("founder_pool.dispatch_sourcing_jobs.redis_health_failed error=%s", exc)

        logger.info(
            "founder_pool.dispatch_sourcing_jobs.end dispatched=%s",
            len(dispatched),
        )
        return {"dispatched": dispatched, "now": now.isoformat()}
    finally:
        db.close()


@app.task(
    bind=True,
    max_retries=SOURCING_MAX_RETRIES,
    default_retry_delay=SOURCING_RETRY_BASE_DELAY,
    rate_limit="4/m",
)
def refresh_pool_task(
    self,
    sectors: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    geographies: Optional[List[str]] = None,
    risk_appetite: str = "moderate",
    sources: Optional[List[dict[str, str]]] = None,
    thesis_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery task that refreshes the founder pool with AI-sourced recommendations."""
    logger.info("founder_pool.refresh_pool_task.start task_id=%s job_id=%s sources=%s", self.request.id, job_id, sources)
    try:
        pool = refresh_founder_pool(
            sectors=sectors,
            stages=stages,
            geographies=geographies,
            risk_appetite=risk_appetite,
            sources=sources,
            thesis_id=thesis_id,
            job_id=job_id,
        )
    except Exception as exc:
        logger.error("founder_pool.refresh_pool_task.error error=%s", exc)
        maybe_retry(self, exc)

    return {
        "status": "completed",
        "count": len(pool),
        "added": len([i for i in pool if i.status == PoolItemStatus.RECOMMENDED]),
    }
