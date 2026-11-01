import logging
from typing import Any, Dict

from celery_app import app
from ai_policy import manual_allowed, skipped_manual_required

logger = logging.getLogger(__name__)


def estimate_founder_scores(founder_id: str):
    # Loading pages and replaying legacy jobs must not initialize an AI client.
    from estimation import estimate_founder_scores as estimate
    return estimate(founder_id)


@app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    rate_limit="4/m",
)
def run_estimate(self, founder_id: str, manual_intent: str = None) -> Dict[str, Any]:
    """Celery task that runs AI estimation for a founder and recalculates the score.

    Runs only for a fresh estimate grant issued by the protected manual API.
    """
    if not manual_allowed(manual_intent, ("estimate",), founder_id, self.request.id):
        return skipped_manual_required(founder_id=founder_id)
    logger.info("estimation.task.start founder_id=%s task_id=%s", founder_id, self.request.id)
    try:
        result = estimate_founder_scores(founder_id)
    except Exception as exc:
        logger.error("estimation.task.error founder_id=%s error=%s", founder_id, exc)
        raise self.retry(exc=exc, countdown=15)

    if result is None:
        logger.info("estimation.task.skipped founder_id=%s", founder_id)
        return {"founder_id": founder_id, "status": "skipped"}

    logger.info(
        "estimation.task.end founder_id=%s score=%s confidence=%s",
        founder_id,
        result.get("founder_score"),
        result.get("overall_confidence"),
    )
    return {"founder_id": founder_id, "status": "completed", "snapshot": result}
