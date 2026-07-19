import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

import db_models
from models import (
    Claim,
    DimensionBreakdown,
    EvidenceItem,
    Founder,
    FounderPoolItem,
    OpportunityScreen,
    ScoreSnapshot,
    SocialFootprint,
    SocialMediaBackground,
    Thesis,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Founders
# -----------------------------------------------------------------------------

def create_founder(db: Session, founder: Founder) -> db_models.Founder:
    db_founder = db_models.Founder(
        id=founder.id,
        name=founder.name,
        email=founder.email,
        current_company=founder.current_company,
        role=founder.role,
        location=founder.location,
        location_city=founder.location_city,
        linkedin_url=founder.linkedin_url,
        github_url=founder.github_url,
        ai_research_summary=founder.ai_research_summary,
        ai_research_sources=founder.ai_research_sources or [],
        social_background_id=founder.social_background_id,
        latest_score_snapshot_id=founder.latest_score_snapshot.id if founder.latest_score_snapshot else None,
    )
    db.add(db_founder)
    db.commit()
    db.refresh(db_founder)
    return db_founder


def get_founder(db: Session, founder_id: str) -> Optional[db_models.Founder]:
    return db.query(db_models.Founder).filter(db_models.Founder.id == founder_id).first()


def list_founders(db: Session) -> List[db_models.Founder]:
    return db.query(db_models.Founder).order_by(db_models.Founder.created_at.desc()).all()


def update_founder(db: Session, founder_id: str, updates: Dict) -> Optional[db_models.Founder]:
    db_founder = get_founder(db, founder_id)
    if not db_founder:
        return None
    for key, value in updates.items():
        setattr(db_founder, key, value)
    db.commit()
    db.refresh(db_founder)
    return db_founder


def founder_to_pydantic(db: Session, db_founder: db_models.Founder) -> Founder:
    data = {
        "id": db_founder.id,
        "name": db_founder.name,
        "email": db_founder.email,
        "current_company": db_founder.current_company,
        "role": db_founder.role,
        "location": db_founder.location,
        "location_city": db_founder.location_city,
        "linkedin_url": db_founder.linkedin_url,
        "github_url": db_founder.github_url,
        "ai_research_summary": db_founder.ai_research_summary,
        "ai_research_sources": db_founder.ai_research_sources or [],
        "social_background_id": db_founder.social_background_id,
    }
    if db_founder.latest_score_snapshot_id:
        db_snapshot = get_score_snapshot(db, db_founder.latest_score_snapshot_id)
        if db_snapshot:
            data["latest_score_snapshot"] = score_snapshot_to_pydantic(db_snapshot)
    return Founder(**data)


# -----------------------------------------------------------------------------
# Theses
# -----------------------------------------------------------------------------

def create_thesis(db: Session, thesis: Thesis) -> db_models.Thesis:
    db_thesis = db_models.Thesis(
        id=thesis.id,
        name=thesis.name,
        sectors=thesis.sectors,
        stages=thesis.stages,
        geographies=thesis.geographies,
        check_size_min=thesis.check_size_min,
        check_size_max=thesis.check_size_max,
        risk_appetite=thesis.risk_appetite,
        min_evidence_requirements=thesis.min_evidence_requirements or {},
        created_at=thesis.created_at,
    )
    db.add(db_thesis)
    db.commit()
    db.refresh(db_thesis)
    return db_thesis


def get_thesis(db: Session, thesis_id: str) -> Optional[db_models.Thesis]:
    return db.query(db_models.Thesis).filter(db_models.Thesis.id == thesis_id).first()


def list_theses(db: Session) -> List[db_models.Thesis]:
    return db.query(db_models.Thesis).order_by(db_models.Thesis.created_at.desc()).all()


def thesis_to_pydantic(db_thesis: db_models.Thesis) -> Thesis:
    return Thesis(
        id=db_thesis.id,
        name=db_thesis.name,
        sectors=db_thesis.sectors or [],
        stages=db_thesis.stages or [],
        geographies=db_thesis.geographies or [],
        check_size_min=db_thesis.check_size_min,
        check_size_max=db_thesis.check_size_max,
        risk_appetite=db_thesis.risk_appetite,
        min_evidence_requirements=db_thesis.min_evidence_requirements or {},
        created_at=db_thesis.created_at,
    )


# -----------------------------------------------------------------------------
# Evidence
# -----------------------------------------------------------------------------

def evidence_to_db(founder_id: str, item: EvidenceItem) -> db_models.EvidenceItem:
    return db_models.EvidenceItem(
        id=item.id,
        founder_id=founder_id,
        dimension=item.dimension.value,
        observation=item.observation,
        source_type=item.source_type,
        source_id=item.source_id,
        source_locator=item.source_locator,
        evidence_type=item.evidence_type.value,
        rubric_level=item.rubric_level,
        source_trust=item.source_trust,
        task_relevance=item.task_relevance,
        recency_factor=item.recency_factor,
        independence_group=item.independence_group,
        polarity=item.polarity.value,
        status=item.status.value,
        counter_evidence=item.counter_evidence,
        unknowns=item.unknowns,
        created_at=item.created_at,
    )


def evidence_to_pydantic(db_item: db_models.EvidenceItem) -> EvidenceItem:
    from models import Dimension, EvidenceStatus, EvidenceType

    return EvidenceItem(
        id=db_item.id,
        founder_id=db_item.founder_id,
        dimension=Dimension(db_item.dimension),
        observation=db_item.observation,
        source_type=db_item.source_type,
        source_id=db_item.source_id,
        source_locator=db_item.source_locator,
        evidence_type=EvidenceType(db_item.evidence_type),
        rubric_level=db_item.rubric_level,
        source_trust=db_item.source_trust,
        task_relevance=db_item.task_relevance,
        recency_factor=db_item.recency_factor,
        independence_group=db_item.independence_group,
        polarity=EvidenceStatus(db_item.polarity),
        status=EvidenceStatus(db_item.status),
        counter_evidence=db_item.counter_evidence,
        unknowns=db_item.unknowns,
        created_at=db_item.created_at,
    )


def add_evidence_items(db: Session, founder_id: str, items: List[EvidenceItem]) -> List[db_models.EvidenceItem]:
    db_items = [evidence_to_db(founder_id, item) for item in items]
    db.add_all(db_items)
    db.commit()
    for item in db_items:
        db.refresh(item)
    return db_items


def list_evidence_for_founder(db: Session, founder_id: str) -> List[EvidenceItem]:
    db_items = (
        db.query(db_models.EvidenceItem)
        .filter(db_models.EvidenceItem.founder_id == founder_id)
        .order_by(db_models.EvidenceItem.created_at.asc())
        .all()
    )
    return [evidence_to_pydantic(item) for item in db_items]


# -----------------------------------------------------------------------------
# Score Snapshots
# -----------------------------------------------------------------------------

def score_snapshot_to_db(snapshot: ScoreSnapshot) -> db_models.ScoreSnapshot:
    return db_models.ScoreSnapshot(
        id=snapshot.id,
        founder_id=snapshot.founder_id,
        rubric_version=snapshot.rubric_version,
        prompt_version=snapshot.prompt_version,
        model_version=snapshot.model_version,
        created_at=snapshot.created_at,
        founder_score=snapshot.founder_score,
        evidence_band_low=snapshot.evidence_band_low,
        evidence_band_high=snapshot.evidence_band_high,
        overall_confidence=snapshot.overall_confidence,
        evidence_coverage=snapshot.evidence_coverage,
        trend=snapshot.trend,
        dimension_breakdowns=[bd.model_dump(mode="json") for bd in snapshot.dimension_breakdowns],
        evidence_items=[item.model_dump(mode="json") for item in snapshot.evidence_items],
        change_explanation=snapshot.change_explanation,
    )


def score_snapshot_to_pydantic(db_snapshot: db_models.ScoreSnapshot) -> ScoreSnapshot:
    return ScoreSnapshot(
        id=db_snapshot.id,
        founder_id=db_snapshot.founder_id,
        rubric_version=db_snapshot.rubric_version,
        prompt_version=db_snapshot.prompt_version,
        model_version=db_snapshot.model_version,
        created_at=db_snapshot.created_at,
        founder_score=db_snapshot.founder_score,
        evidence_band_low=db_snapshot.evidence_band_low,
        evidence_band_high=db_snapshot.evidence_band_high,
        overall_confidence=db_snapshot.overall_confidence,
        evidence_coverage=db_snapshot.evidence_coverage,
        trend=db_snapshot.trend,
        dimension_breakdowns=[DimensionBreakdown(**bd) for bd in (db_snapshot.dimension_breakdowns or [])],
        evidence_items=[EvidenceItem(**item) for item in (db_snapshot.evidence_items or [])],
        change_explanation=db_snapshot.change_explanation,
    )


def create_score_snapshot(db: Session, snapshot: ScoreSnapshot) -> db_models.ScoreSnapshot:
    db_snapshot = score_snapshot_to_db(snapshot)
    db.add(db_snapshot)
    db.commit()
    db.refresh(db_snapshot)
    return db_snapshot


def get_score_snapshot(db: Session, snapshot_id: str) -> Optional[db_models.ScoreSnapshot]:
    return db.query(db_models.ScoreSnapshot).filter(db_models.ScoreSnapshot.id == snapshot_id).first()


def list_score_snapshots_for_founder(db: Session, founder_id: str) -> List[ScoreSnapshot]:
    db_snapshots = (
        db.query(db_models.ScoreSnapshot)
        .filter(db_models.ScoreSnapshot.founder_id == founder_id)
        .order_by(db_models.ScoreSnapshot.created_at.asc())
        .all()
    )
    return [score_snapshot_to_pydantic(s) for s in db_snapshots]


# -----------------------------------------------------------------------------
# Social Media Backgrounds
# -----------------------------------------------------------------------------

def social_background_to_db(background: SocialMediaBackground) -> db_models.SocialMediaBackground:
    return db_models.SocialMediaBackground(
        id=background.id,
        founder_id=background.founder_id,
        status=background.status,
        linkedin_url=background.linkedin_url,
        github_url=background.github_url,
        summary=background.summary,
        footprints=[fp.model_dump(mode="json") for fp in background.footprints],
        evidence_items=[item.model_dump(mode="json") for item in background.evidence_items],
        score_snapshot=background.score_snapshot.model_dump(mode="json") if background.score_snapshot else None,
        error_message=background.error_message,
        created_at=background.created_at,
        updated_at=background.updated_at,
    )


def social_background_to_pydantic(db_background: db_models.SocialMediaBackground) -> SocialMediaBackground:
    return SocialMediaBackground(
        id=db_background.id,
        founder_id=db_background.founder_id,
        status=db_background.status,
        linkedin_url=db_background.linkedin_url,
        github_url=db_background.github_url,
        summary=db_background.summary,
        footprints=[SocialFootprint(**fp) for fp in (db_background.footprints or [])],
        evidence_items=[EvidenceItem(**item) for item in (db_background.evidence_items or [])],
        score_snapshot=ScoreSnapshot(**db_background.score_snapshot) if db_background.score_snapshot else None,
        error_message=db_background.error_message,
        created_at=db_background.created_at,
        updated_at=db_background.updated_at,
    )


def create_social_background(db: Session, background: SocialMediaBackground) -> db_models.SocialMediaBackground:
    db_background = social_background_to_db(background)
    db.add(db_background)
    db.commit()
    db.refresh(db_background)
    return db_background


def get_social_background_by_founder(db: Session, founder_id: str) -> Optional[db_models.SocialMediaBackground]:
    return (
        db.query(db_models.SocialMediaBackground)
        .filter(db_models.SocialMediaBackground.founder_id == founder_id)
        .order_by(db_models.SocialMediaBackground.created_at.desc())
        .first()
    )


def update_social_background(db: Session, background: SocialMediaBackground) -> db_models.SocialMediaBackground:
    db_background = db.query(db_models.SocialMediaBackground).filter(
        db_models.SocialMediaBackground.id == background.id
    ).first()
    if not db_background:
        return create_social_background(db, background)

    db_background.status = background.status
    db_background.linkedin_url = background.linkedin_url
    db_background.github_url = background.github_url
    db_background.summary = background.summary
    db_background.footprints = [fp.model_dump(mode="json") for fp in background.footprints]
    db_background.evidence_items = [item.model_dump(mode="json") for item in background.evidence_items]
    db_background.score_snapshot = (
        background.score_snapshot.model_dump(mode="json") if background.score_snapshot else None
    )
    db_background.error_message = background.error_message
    db.commit()
    db.refresh(db_background)
    return db_background


# -----------------------------------------------------------------------------
# Founder Pool
# -----------------------------------------------------------------------------

def pool_item_to_db(item: FounderPoolItem) -> db_models.FounderPoolItem:
    return db_models.FounderPoolItem(
        id=item.id,
        name=item.name,
        email=item.email,
        current_company=item.current_company,
        role=item.role,
        location=item.location,
        linkedin_url=item.linkedin_url,
        github_url=item.github_url,
        source_url=item.source_url,
        reason=item.reason,
        thesis_id=item.thesis_id,
        status=item.status.value,
        created_at=item.created_at,
    )


def pool_item_to_pydantic(db_item: db_models.FounderPoolItem) -> FounderPoolItem:
    from models import PoolItemStatus

    return FounderPoolItem(
        id=db_item.id,
        name=db_item.name,
        email=db_item.email,
        current_company=db_item.current_company,
        role=db_item.role,
        location=db_item.location,
        linkedin_url=db_item.linkedin_url,
        github_url=db_item.github_url,
        source_url=db_item.source_url,
        reason=db_item.reason,
        thesis_id=db_item.thesis_id,
        status=PoolItemStatus(db_item.status),
        created_at=db_item.created_at,
    )


def create_pool_items(db: Session, items: List[FounderPoolItem]) -> List[db_models.FounderPoolItem]:
    db_items = [pool_item_to_db(item) for item in items]
    db.add_all(db_items)
    db.commit()
    for item in db_items:
        db.refresh(item)
    return db_items


def list_pool_items(db: Session, status: Optional[str] = None) -> List[db_models.FounderPoolItem]:
    query = db.query(db_models.FounderPoolItem)
    if status:
        query = query.filter(db_models.FounderPoolItem.status == status)
    return query.order_by(db_models.FounderPoolItem.created_at.desc()).all()


def get_pool_item(db: Session, item_id: str) -> Optional[db_models.FounderPoolItem]:
    return db.query(db_models.FounderPoolItem).filter(db_models.FounderPoolItem.id == item_id).first()


def update_pool_item_status(db: Session, item_id: str, status: str) -> Optional[db_models.FounderPoolItem]:
    db_item = get_pool_item(db, item_id)
    if not db_item:
        return None
    db_item.status = status
    db.commit()
    db.refresh(db_item)
    return db_item


def pool_item_exists(db: Session, name: str, company: Optional[str], linkedin: Optional[str]) -> bool:
    from sqlalchemy import func

    name_norm = (name or "").lower().strip()
    company_norm = (company or "").lower().strip()
    linkedin_norm = (linkedin or "").lower().strip()

    existing = (
        db.query(db_models.FounderPoolItem)
        .filter(
            func.lower(func.trim(db_models.FounderPoolItem.name)) == name_norm,
            func.lower(func.trim(db_models.FounderPoolItem.current_company)) == company_norm,
            func.lower(func.trim(db_models.FounderPoolItem.linkedin_url)) == linkedin_norm,
        )
        .first()
    )
    return existing is not None


# -----------------------------------------------------------------------------
# Opportunities
# -----------------------------------------------------------------------------

def opportunity_to_db(opp: OpportunityScreen) -> db_models.Opportunity:
    return db_models.Opportunity(
        id=opp.opportunity_id,
        founder_id=opp.founder_id,
        founder_score=opp.founder_score,
        founder_confidence=opp.founder_confidence,
        founder_market_fit=opp.founder_market_fit.model_dump(mode="json"),
        team_completeness=opp.team_completeness.model_dump(mode="json"),
        market_posture=opp.market_posture,
        market_confidence=opp.market_confidence,
        idea_vs_market_posture=opp.idea_vs_market_posture,
        idea_vs_market_confidence=opp.idea_vs_market_confidence,
        next_founder_action=opp.next_founder_action,
    )


def opportunity_to_pydantic(db_opp: db_models.Opportunity) -> OpportunityScreen:
    from models import FounderMarketFit, TeamCompleteness

    return OpportunityScreen(
        opportunity_id=db_opp.id,
        founder_id=db_opp.founder_id,
        founder_score=db_opp.founder_score,
        founder_confidence=db_opp.founder_confidence,
        founder_market_fit=FounderMarketFit(**(db_opp.founder_market_fit or {})),
        team_completeness=TeamCompleteness(**(db_opp.team_completeness or {})),
        market_posture=db_opp.market_posture,
        market_confidence=db_opp.market_confidence,
        idea_vs_market_posture=db_opp.idea_vs_market_posture,
        idea_vs_market_confidence=db_opp.idea_vs_market_confidence,
        next_founder_action=db_opp.next_founder_action,
    )


def create_or_update_opportunity(db: Session, opp: OpportunityScreen) -> db_models.Opportunity:
    db_opp = db.query(db_models.Opportunity).filter(db_models.Opportunity.id == opp.opportunity_id).first()
    if db_opp:
        db_opp.founder_id = opp.founder_id
        db_opp.founder_score = opp.founder_score
        db_opp.founder_confidence = opp.founder_confidence
        db_opp.founder_market_fit = opp.founder_market_fit.model_dump(mode="json")
        db_opp.team_completeness = opp.team_completeness.model_dump(mode="json")
        db_opp.market_posture = opp.market_posture
        db_opp.market_confidence = opp.market_confidence
        db_opp.idea_vs_market_posture = opp.idea_vs_market_posture
        db_opp.idea_vs_market_confidence = opp.idea_vs_market_confidence
        db_opp.next_founder_action = opp.next_founder_action
    else:
        db_opp = opportunity_to_db(opp)
        db.add(db_opp)
    db.commit()
    db.refresh(db_opp)
    return db_opp


def get_opportunity(db: Session, opportunity_id: str) -> Optional[db_models.Opportunity]:
    return db.query(db_models.Opportunity).filter(db_models.Opportunity.id == opportunity_id).first()


# -----------------------------------------------------------------------------
# Claims
# -----------------------------------------------------------------------------

def claim_to_db(claim: Claim) -> db_models.Claim:
    return db_models.Claim(
        id=claim.id,
        opportunity_id=claim.opportunity_id,
        claim=claim.claim,
        source=claim.source,
        trust_status=claim.trust_status.value,
        confidence=claim.confidence,
        contradiction=claim.contradiction,
        owner=claim.owner,
        next_action=claim.next_action,
    )


def claim_to_pydantic(db_claim: db_models.Claim) -> Claim:
    from models import TrustStatus

    return Claim(
        id=db_claim.id,
        opportunity_id=db_claim.opportunity_id,
        claim=db_claim.claim,
        source=db_claim.source,
        trust_status=TrustStatus(db_claim.trust_status),
        confidence=db_claim.confidence,
        contradiction=db_claim.contradiction,
        owner=db_claim.owner,
        next_action=db_claim.next_action,
    )


def create_claims(db: Session, claims: List[Claim]) -> List[db_models.Claim]:
    db_claims = [claim_to_db(claim) for claim in claims]
    db.add_all(db_claims)
    db.commit()
    for claim in db_claims:
        db.refresh(claim)
    return db_claims


def list_claims_for_opportunity(db: Session, opportunity_id: str) -> List[Claim]:
    db_claims = (
        db.query(db_models.Claim)
        .filter(db_models.Claim.opportunity_id == opportunity_id)
        .all()
    )
    return [claim_to_pydantic(c) for c in db_claims]
