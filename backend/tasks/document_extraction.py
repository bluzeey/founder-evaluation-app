import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from celery_app import app
from database import SessionLocal
import crud
from document_extractor import extract_text
from models import Claim, EvidenceItem, Founder, SourcingJob, TrustStatus
from estimation import estimate_founder_scores
from research import DocumentAgent
from research.extractor import create_founder_from_research, evidence_from_llm
from tasks.retry_utils import (
    DOCUMENT_MAX_RETRIES,
    DOCUMENT_RETRY_BASE_DELAY,
    maybe_retry,
)

logger = logging.getLogger(__name__)


def _trust_status_from_string(value: Optional[str]) -> TrustStatus:
    try:
        return TrustStatus(value or "founder_reported")
    except ValueError:
        return TrustStatus.FOUNDER_REPORTED


@app.task(
    bind=True,
    max_retries=DOCUMENT_MAX_RETRIES,
    default_retry_delay=DOCUMENT_RETRY_BASE_DELAY,
    rate_limit="4/m",
)
def extract_document(
    self,
    file_bytes_b64: str,
    filename: str,
    opportunity_id: str,
    founder_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery task that extracts claims and evidence from an uploaded document.

    The file bytes are base64-encoded because Celery JSON serializer cannot handle
    raw bytes. The file itself is not persisted; only the extracted structured data
    is stored in the database.
    """
    import base64

    db = SessionLocal()
    try:
        file_bytes = base64.b64decode(file_bytes_b64)
        text = extract_text(file_bytes, filename)
        if text is None:
            logger.error("document_extraction.unsupported_type filename=%s", filename)
            return {
                "status": "failed",
                "error": f"Unsupported file type: {filename}",
            }

        logger.info(
            "document_extraction.task.start filename=%s opportunity_id=%s founder_id=%s text_chars=%s",
            filename,
            opportunity_id,
            founder_id,
            len(text),
        )

        try:
            agent = DocumentAgent()
            result = agent.extract(text, filename=filename)
        except Exception as exc:
            logger.error("document_extraction.task.error error=%s", exc)
            maybe_retry(self, exc, base_delay=DOCUMENT_RETRY_BASE_DELAY)

        # Create claims from extracted data.
        raw_claims = result.get("claims", []) or []
        claims = []
        for rc in raw_claims:
            claim = Claim(
                id=f"clm_{uuid.uuid4().hex[:8]}",
                opportunity_id=opportunity_id,
                founder_id=founder_id,
                claim=rc.get("claim", ""),
                source=rc.get("source", filename),
                trust_status=_trust_status_from_string(rc.get("trust_status")),
                confidence=float(rc.get("confidence", 0.35) or 0.35),
                contradiction=rc.get("contradiction") or None,
                owner=rc.get("owner") or None,
                next_action=rc.get("next_action") or None,
            )
            claims.append(claim)
        if claims:
            crud.create_claims(db, claims)

        # Create evidence items from extracted data.
        raw_evidence = result.get("evidence", []) or []
        evidence_items = []
        for item in raw_evidence:
            evidence_items.append(evidence_from_llm(founder_id or opportunity_id, item))
        if founder_id and evidence_items:
            crud.add_evidence_items(db, founder_id, evidence_items)
            all_items = crud.list_evidence_for_founder(db, founder_id)
            db_founder = crud.get_founder(db, founder_id)
            previous = (
                crud.score_snapshot_to_pydantic(snapshot)
                if db_founder.latest_score_snapshot_id
                and (snapshot := crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id))
                else None
            )
            from scoring import calculate_founder_score

            snapshot = calculate_founder_score(founder_id, all_items, previous)
            db_snapshot = crud.create_score_snapshot(db, snapshot)
            crud.update_founder(db, founder_id, {"latest_score_snapshot_id": db_snapshot.id})

            # Keep opportunity scores in sync with the new evidence.
            opps = crud.list_opportunities(db, founder_id)
            for db_opp in opps:
                db_opp.founder_score = snapshot.founder_score
                db_opp.founder_confidence = snapshot.overall_confidence
            db.commit()

        # Always fill remaining unknown/low-confidence dimensions with AI estimates
        # when we have a founder. This covers the common case where the LLM
        # returned claims but no direct evidence array, as well as dimensions
        # that the direct evidence did not cover. estimate_founder_scores gates
        # internally on evidence count + confidence, so this is safe to call
        # even when evidence_items was non-empty above.
        if founder_id:
            estimate_founder_scores(founder_id, db=db)

        # Optionally update founder profile if founder_id is provided.
        if founder_id:
            db_founder = crud.get_founder(db, founder_id)
            if db_founder:
                profile = result.get("profile", {}) or {}
                updates = {}
                if profile.get("name") and not db_founder.name:
                    updates["name"] = profile["name"]
                if profile.get("email") and not db_founder.email:
                    updates["email"] = profile["email"]
                if profile.get("current_company") and not db_founder.current_company:
                    updates["current_company"] = profile["current_company"]
                if profile.get("role") and not db_founder.role:
                    updates["role"] = profile["role"]
                if profile.get("location") and not db_founder.location:
                    updates["location"] = profile["location"]
                if profile.get("linkedin_url") and not db_founder.linkedin_url:
                    updates["linkedin_url"] = profile["linkedin_url"]
                if profile.get("github_url") and not db_founder.github_url:
                    updates["github_url"] = profile["github_url"]
                if updates:
                    crud.update_founder(db, founder_id, updates)

        logger.info(
            "document_extraction.task.end filename=%s claims=%s evidence=%s",
            filename,
            len(claims),
            len(evidence_items),
        )
        return {
            "status": "completed",
            "opportunity_id": opportunity_id,
            "founder_id": founder_id,
            "claims_count": len(claims),
            "evidence_count": len(evidence_items),
            "summary": result.get("summary", ""),
        }
    finally:
        db.close()
