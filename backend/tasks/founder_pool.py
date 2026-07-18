import json
import os
import uuid
from typing import Any, Dict, List, Optional

import redis

from celery_app import app
from models import FounderPoolItem, PoolItemStatus
from research import SourcingAgent

REDIS_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
POOL_KEY = "founder_pool"


def _redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def load_founder_pool() -> List[FounderPoolItem]:
    """Load the current founder pool from Redis."""
    client = _redis_client()
    raw = client.get(POOL_KEY)
    if not raw:
        return []
    data = json.loads(raw)
    return [FounderPoolItem(**item) for item in data]


def save_founder_pool(pool: List[FounderPoolItem]) -> None:
    """Persist the founder pool to Redis."""
    client = _redis_client()
    data = [item.model_dump(mode="json") for item in pool]
    client.set(POOL_KEY, json.dumps(data))


def refresh_founder_pool(
    sectors: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    geographies: Optional[List[str]] = None,
    risk_appetite: str = "moderate",
    thesis_id: Optional[str] = None,
) -> List[FounderPoolItem]:
    """Run the sourcing agent and append new recommendations to the pool.

    Existing recommended items are kept; new items are appended at the front.
    Approved/dismissed items are preserved.
    """
    sectors = sectors or ["B2B SaaS", "AI Infrastructure"]
    stages = stages or ["pre-seed", "seed"]
    geographies = geographies or ["Global"]

    agent = SourcingAgent()
    result = agent.discover(
        sectors=sectors,
        stages=stages,
        geographies=geographies,
        risk_appetite=risk_appetite,
    )

    recommendations = result.get("recommendations", []) or []
    new_items = []
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
        new_items.append(item)

    existing = load_founder_pool()
    kept = [item for item in existing if item.status != PoolItemStatus.RECOMMENDED]
    pool = new_items + kept
    save_founder_pool(pool)
    return pool


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
    try:
        pool = refresh_founder_pool(
            sectors=sectors,
            stages=stages,
            geographies=geographies,
            risk_appetite=risk_appetite,
            thesis_id=thesis_id,
        )
    except Exception as exc:
        raise self.retry(exc=exc)

    return {
        "status": "completed",
        "count": len(pool),
        "added": len([i for i in pool if i.status == PoolItemStatus.RECOMMENDED]),
    }
