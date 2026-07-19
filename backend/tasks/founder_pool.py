import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import redis

from celery_app import app
from database import SessionLocal
import crud
import db_models
from models import FounderPoolItem, PoolItemStatus
from research import SourcingAgent

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


def refresh_founder_pool(
    sectors: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    geographies: Optional[List[str]] = None,
    risk_appetite: str = "moderate",
    thesis_id: Optional[str] = None,
) -> List[FounderPoolItem]:
    """Run the sourcing agent and append new recommendations to the database pool.

    Existing recommended items are replaced; approved/dismissed items are preserved.
    Duplicate candidates are skipped.
    """
    sectors = sectors or ["B2B SaaS", "AI Infrastructure"]
    stages = stages or ["pre-seed", "seed"]
    geographies = geographies or ["Global"]

    logger.info(
        "founder_pool.refresh.start sectors=%s stages=%s geographies=%s risk=%s thesis_id=%s",
        sectors,
        stages,
        geographies,
        risk_appetite,
        thesis_id,
    )

    if not acquire_refresh_lock():
        logger.warning("founder_pool.refresh.skip_locked")
        return load_founder_pool()

    db = SessionLocal()
    try:
        existing = crud.list_pool_items(db)
        logger.info("founder_pool.refresh.existing_count count=%s", len(existing))

        agent = SourcingAgent()
        result = agent.discover(
            sectors=sectors,
            stages=stages,
            geographies=geographies,
            risk_appetite=risk_appetite,
        )

        recommendations = result.get("recommendations", []) or []

        # Build a set of existing dedup keys across the whole pool.
        existing_keys = {_dedup_key(crud.pool_item_to_pydantic(item)) for item in existing}

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
                reason=rec.get("reason", "") or "",
                thesis_id=thesis_id,
            )
            key = _dedup_key(item)
            if key in existing_keys or crud.pool_item_exists(db, item.name, item.current_company, item.linkedin_url):
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
        if new_items:
            db.query(db_models.FounderPoolItem).filter(
                db_models.FounderPoolItem.status == PoolItemStatus.RECOMMENDED.value
            ).delete(synchronize_session=False)
            crud.create_pool_items(db, new_items)

        db.commit()

        logger.info(
            "founder_pool.refresh.end added=%s skipped=%s total=%s",
            len(new_items),
            skipped,
            len(crud.list_pool_items(db)),
        )
        return load_founder_pool()
    finally:
        release_refresh_lock()
        db.close()


@app.task(bind=True, max_retries=2, default_retry_delay=5)
def refresh_pool_task(
    self,
    sectors: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    geographies: Optional[List[str]] = None,
    risk_appetite: str = "moderate",
    thesis_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery task that refreshes the founder pool with AI-sourced recommendations."""
    logger.info("founder_pool.refresh_pool_task.start task_id=%s", self.request.id)
    try:
        pool = refresh_founder_pool(
            sectors=sectors,
            stages=stages,
            geographies=geographies,
            risk_appetite=risk_appetite,
            thesis_id=thesis_id,
        )
    except Exception as exc:
        logger.error("founder_pool.refresh_pool_task.error error=%s", exc)
        raise self.retry(exc=exc)

    return {
        "status": "completed",
        "count": len(pool),
        "added": len([i for i in pool if i.status == PoolItemStatus.RECOMMENDED]),
    }
