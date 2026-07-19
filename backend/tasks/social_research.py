import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis

from celery_app import app
from models import SocialMediaBackground
from research import SocialAgent, create_social_background
from scoring import calculate_founder_score

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


def _redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def _key(founder_id: str) -> str:
    return f"founder:social_background:{founder_id}"


def store_social_background(background: SocialMediaBackground) -> None:
    """Persist a SocialMediaBackground record to Redis."""
    client = _redis_client()
    data = background.model_dump(mode="json")
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.set(_key(background.founder_id), json.dumps(data))
    logger.info(
        "social_research.store_background founder_id=%s status=%s",
        background.founder_id,
        background.status,
    )


def load_social_background(founder_id: str) -> Optional[SocialMediaBackground]:
    """Load the latest SocialMediaBackground for a founder from Redis."""
    client = _redis_client()
    raw = client.get(_key(founder_id))
    if not raw:
        return None
    data = json.loads(raw)
    return SocialMediaBackground(**data)


@app.task(bind=True, max_retries=2, default_retry_delay=5)
def research_social_background(
    self,
    founder_id: str,
    name: str,
    email: str,
    linkedin_url: Optional[str],
    github_url: Optional[str],
    auto_score: bool = True,
) -> Dict[str, Any]:
    """Celery task that researches a founder's LinkedIn/GitHub footprint.

    Stores the SocialMediaBackground in Redis and optionally recalculates the
    founder score from the extracted evidence.
    """
    pending = SocialMediaBackground(
        id=f"soc_{uuid.uuid4().hex[:8]}",
        founder_id=founder_id,
        status="running",
        linkedin_url=linkedin_url,
        github_url=github_url,
    )
    store_social_background(pending)
    logger.info("social_research.task.start founder_id=%s task_id=%s", founder_id, self.request.id)

    try:
        agent = SocialAgent()
        result = agent.research(
            name=name,
            linkedin_url=linkedin_url,
            github_url=github_url,
        )
    except Exception as exc:
        logger.error("social_research.task.error founder_id=%s error=%s", founder_id, exc)
        failed = SocialMediaBackground(
            id=pending.id,
            founder_id=founder_id,
            status="failed",
            linkedin_url=linkedin_url,
            github_url=github_url,
            error_message=str(exc),
        )
        store_social_background(failed)
        raise self.retry(exc=exc)

    background = create_social_background(
        founder_id=founder_id,
        result=result,
        linkedin_url=linkedin_url,
        github_url=github_url,
        status="completed",
    )

    # Optionally compute a score snapshot from the social evidence.
    if auto_score and background.evidence_items:
        background.score_snapshot = calculate_founder_score(
            founder_id, background.evidence_items
        )

    store_social_background(background)
    logger.info(
        "social_research.task.end founder_id=%s status=%s evidence=%s scored=%s",
        founder_id,
        background.status,
        len(background.evidence_items),
        background.score_snapshot is not None,
    )
    return background.model_dump(mode="json")
