import logging
from typing import Optional

import crud
from database import SessionLocal
from scoring import calculate_founder_score
from research.founder_estimator import AIFounderEstimator

logger = logging.getLogger(__name__)

_estimator = AIFounderEstimator()


def should_estimate_founder(db, founder_id: str) -> bool:
    """Decide whether to run an AI estimate for a founder."""
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        return False
    founder = crud.founder_to_pydantic(db, db_founder)
    existing = crud.list_evidence_for_founder(db, founder_id)
    snapshot = founder.latest_score_snapshot
    # If we already have plenty of hard evidence and decent confidence, skip.
    if len(existing) >= 8 and snapshot and snapshot.overall_confidence >= 0.3:
        logger.info(
            "estimation.skip founder_id=%s evidence=%s confidence=%s",
            founder_id,
            len(existing),
            snapshot.overall_confidence,
        )
        return False
    return True


def estimate_founder_scores(
    founder_id: str, db=None
) -> Optional[dict]:
    """Generate AI-estimated evidence for a founder and recalculate the score.

    Returns the new score snapshot as a dict, or None if estimation was skipped
    or failed.
    """
    should_close = db is None
    session = db if db is not None else SessionLocal()
    try:
        if not should_estimate_founder(session, founder_id):
            return None

        db_founder = crud.get_founder(session, founder_id)
        founder = crud.founder_to_pydantic(session, db_founder)

        source_reason = founder.source_reason
        research_summary = founder.ai_research_summary

        social_summary = None
        if db_founder.social_background_id:
            db_bg = crud.get_social_background_by_founder(session, founder_id)
            if db_bg:
                social_summary = db_bg.summary

        claims = crud.list_claims_for_founder(session, founder_id)

        evidence_items = _estimator.estimate(
            founder,
            source_reason=source_reason,
            research_summary=research_summary,
            social_summary=social_summary,
            claims=claims,
        )
        if not evidence_items:
            logger.info("estimation.no_items founder_id=%s", founder_id)
            return None

        crud.add_evidence_items(session, founder_id, evidence_items)
        all_items = crud.list_evidence_for_founder(session, founder_id)

        previous = founder.latest_score_snapshot
        new_snapshot = calculate_founder_score(founder_id, all_items, previous)
        db_snapshot = crud.create_score_snapshot(session, new_snapshot)
        crud.update_founder(
            session, founder_id, {"latest_score_snapshot_id": db_snapshot.id}
        )

        # Keep any opportunities in sync with the new score.
        opps = crud.list_opportunities(session, founder_id)
        for db_opp in opps:
            db_opp.founder_score = new_snapshot.founder_score
            db_opp.founder_confidence = new_snapshot.overall_confidence
        session.commit()

        logger.info(
            "estimation.done founder_id=%s score=%s confidence=%s items=%s",
            founder_id,
            new_snapshot.founder_score,
            new_snapshot.overall_confidence,
            len(evidence_items),
        )
        return new_snapshot.model_dump(mode="json")
    except Exception as exc:
        logger.error("estimation.error founder_id=%s error=%s", founder_id, exc)
        return None
    finally:
        if should_close:
            session.close()
