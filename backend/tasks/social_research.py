import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery_app import app
from database import SessionLocal
import crud
from models import SocialMediaBackground
from research import SocialAgent, create_social_background
from scoring import calculate_founder_score
from tasks.retry_utils import (
    SOCIAL_RESEARCH_MAX_RETRIES,
    SOCIAL_RESEARCH_RETRY_BASE_DELAY,
    maybe_retry,
)

logger = logging.getLogger(__name__)


def store_social_background(background: SocialMediaBackground) -> None:
    """Persist a SocialMediaBackground record to the database."""
    db = SessionLocal()
    try:
        existing = crud.get_social_background_by_founder(db, background.founder_id)
        if existing and existing.id == background.id:
            crud.update_social_background(db, background)
        else:
            crud.create_social_background(db, background)
    finally:
        db.close()


def load_social_background(founder_id: str) -> Optional[SocialMediaBackground]:
    """Load the latest SocialMediaBackground for a founder from the database."""
    db = SessionLocal()
    try:
        db_background = crud.get_social_background_by_founder(db, founder_id)
        if not db_background:
            return None
        return crud.social_background_to_pydantic(db_background)
    finally:
        db.close()


@app.task(
    bind=True,
    max_retries=SOCIAL_RESEARCH_MAX_RETRIES,
    default_retry_delay=SOCIAL_RESEARCH_RETRY_BASE_DELAY,
    rate_limit="4/m",
)
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

    Stores the SocialMediaBackground in the database and optionally recalculates the
    founder score from the extracted evidence.
    """
    db = SessionLocal()
    try:
        pending_id = f"soc_{uuid.uuid4().hex[:8]}"
        pending = SocialMediaBackground(
            id=pending_id,
            founder_id=founder_id,
            status="running",
            linkedin_url=linkedin_url,
            github_url=github_url,
        )
        crud.create_social_background(db, pending)
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
                id=pending_id,
                founder_id=founder_id,
                status="failed",
                linkedin_url=linkedin_url,
                github_url=github_url,
                error_message=str(exc),
            )
            crud.update_social_background(db, failed)
            maybe_retry(self, exc, base_delay=SOCIAL_RESEARCH_RETRY_BASE_DELAY)

        background = create_social_background(
            founder_id=founder_id,
            result=result,
            linkedin_url=linkedin_url,
            github_url=github_url,
            status="completed",
        )
        background.id = pending_id

        # Optionally compute a score snapshot from the social evidence.
        if auto_score and background.evidence_items:
            background.score_snapshot = calculate_founder_score(
                founder_id, background.evidence_items
            )

        crud.update_social_background(db, background)
        logger.info(
            "social_research.task.end founder_id=%s status=%s evidence=%s scored=%s",
            founder_id,
            background.status,
            len(background.evidence_items),
            background.score_snapshot is not None,
        )
        return background.model_dump(mode="json")
    finally:
        db.close()
