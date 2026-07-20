import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, cast, desc, func, or_, String as SAString
from sqlalchemy.orm import Session

import db_models
from models import (
    Claim,
    CsvImportRowError,
    CsvImportResult,
    DimensionBreakdown,
    EnrichmentPolicy,
    EnrichmentRun,
    EvidenceItem,
    Founder,
    FounderDiscoveryFacets,
    FounderDiscoveryItem,
    FounderDiscoveryPage,
    FounderPoolItem,
    FounderScreeningProfile,
    OpportunityScreen,
    RecommendationTrigger,
    ScoreSnapshot,
    ScreeningFundingStatus,
    SocialFootprint,
    SocialMediaBackground,
    SourcingJob,
    SourcingSchedule,
    Thesis,
)
from screening import evaluate_recommendation

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Founders
# -----------------------------------------------------------------------------


def normalize_text_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


def normalize_url_value(value: Optional[str]) -> Optional[str]:
    normalized = normalize_text_value(value)
    if normalized is None:
        return None
    if normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized or None


def create_placeholder_import_email(external_record_id: Optional[str], founder_id: str) -> str:
    token = external_record_id or founder_id
    return f"import+{token.lower()}@founderos.import"

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
        linkedin_url_normalized=normalize_url_value(founder.linkedin_url),
        github_url=founder.github_url,
        source_reason=founder.source_reason,
        source_url=founder.source_url,
        ai_research_summary=founder.ai_research_summary,
        ai_research_sources=founder.ai_research_sources or [],
        social_background_id=founder.social_background_id,
        latest_score_snapshot_id=founder.latest_score_snapshot.id if founder.latest_score_snapshot else None,
        enrichment_policy=founder.enrichment_policy.value if isinstance(founder.enrichment_policy, EnrichmentPolicy) else founder.enrichment_policy,
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
    if "linkedin_url" in updates:
        updates["linkedin_url_normalized"] = normalize_url_value(updates.get("linkedin_url"))
    if "enrichment_policy" in updates and isinstance(updates["enrichment_policy"], EnrichmentPolicy):
        updates["enrichment_policy"] = updates["enrichment_policy"].value
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
        "source_reason": db_founder.source_reason,
        "source_url": db_founder.source_url,
        "ai_research_summary": db_founder.ai_research_summary,
        "ai_research_sources": db_founder.ai_research_sources or [],
        "social_background_id": db_founder.social_background_id,
        "enrichment_policy": db_founder.enrichment_policy,
        "created_at": db_founder.created_at,
        "updated_at": db_founder.updated_at,
    }
    if db_founder.latest_score_snapshot_id:
        db_snapshot = get_score_snapshot(db, db_founder.latest_score_snapshot_id)
        if db_snapshot:
            data["latest_score_snapshot"] = score_snapshot_to_pydantic(db_snapshot)
    return Founder(**data)


def screening_profile_to_pydantic(
    db_profile: db_models.FounderScreeningProfile,
) -> FounderScreeningProfile:
    return FounderScreeningProfile(
        id=db_profile.id,
        founder_id=db_profile.founder_id,
        external_record_id=db_profile.external_record_id,
        project_name=db_profile.project_name,
        project_summary=db_profile.project_summary,
        founder_role=db_profile.founder_role,
        sector=db_profile.sector,
        stage=db_profile.stage,
        source_type=db_profile.source_type,
        institution_or_program=db_profile.institution_or_program,
        school_or_lab=db_profile.school_or_lab,
        cohort_year=db_profile.cohort_year,
        institution_affiliation_basis=db_profile.institution_affiliation_basis,
        city=db_profile.city,
        country=db_profile.country,
        city_basis=db_profile.city_basis,
        city_confidence=db_profile.city_confidence,
        target_market_geography=db_profile.target_market_geography,
        website_url=db_profile.website_url,
        primary_source_url=db_profile.primary_source_url,
        source_locator=db_profile.source_locator,
        source_date=db_profile.source_date,
        funding_status=ScreeningFundingStatus(db_profile.funding_status),
        funding_check_as_of=db_profile.funding_check_as_of,
        funding_check_confidence=db_profile.funding_check_confidence,
        funding_notes=db_profile.funding_notes,
        founder_score=db_profile.founder_score,
        founder_score_rationale=db_profile.founder_score_rationale,
        vision_product_score=db_profile.vision_product_score,
        vision_product_rationale=db_profile.vision_product_rationale,
        differentiation_score=db_profile.differentiation_score,
        differentiation_rationale=db_profile.differentiation_rationale,
        traction_score=db_profile.traction_score,
        traction_rationale=db_profile.traction_rationale,
        evidence_confidence=db_profile.evidence_confidence,
        evidence_coverage=db_profile.evidence_coverage,
        individual_attribution_confidence=db_profile.individual_attribution_confidence,
        evaluation_scope=db_profile.evaluation_scope,
        key_evidence=db_profile.key_evidence or [],
        counter_evidence=db_profile.counter_evidence or [],
        unknowns=db_profile.unknowns or [],
        next_diligence_action=db_profile.next_diligence_action,
        recommended=db_profile.recommended,
        recommendation_trigger=RecommendationTrigger(db_profile.recommendation_trigger),
        recommended_reason=db_profile.recommended_reason,
        evaluation_version=db_profile.evaluation_version,
        pedigree_used_in_scoring=db_profile.pedigree_used_in_scoring,
        import_status=db_profile.import_status,
        research_priority=db_profile.research_priority,
        tags=db_profile.tags or [],
        imported_associate_call_recommended=db_profile.imported_associate_call_recommended,
        imported_recommendation_trigger=db_profile.imported_recommendation_trigger,
        imported_recommended_reason=db_profile.imported_recommended_reason,
        produced_by=db_profile.produced_by,
        import_id=db_profile.import_id,
        created_at=db_profile.created_at,
        updated_at=db_profile.updated_at,
    )


def get_screening_profile(
    db: Session,
    founder_id: str,
    evaluation_version: str = "associate_screen_v1",
) -> Optional[db_models.FounderScreeningProfile]:
    return (
        db.query(db_models.FounderScreeningProfile)
        .filter(
            db_models.FounderScreeningProfile.founder_id == founder_id,
            db_models.FounderScreeningProfile.evaluation_version == evaluation_version,
        )
        .first()
    )


def get_screening_profile_by_external_record_id(
    db: Session,
    external_record_id: str,
) -> Optional[db_models.FounderScreeningProfile]:
    return (
        db.query(db_models.FounderScreeningProfile)
        .filter(db_models.FounderScreeningProfile.external_record_id == external_record_id)
        .first()
    )


def create_or_update_screening_profile(
    db: Session,
    founder_id: str,
    profile_data: Dict[str, Any],
    commit: bool = True,
) -> db_models.FounderScreeningProfile:
    evaluation_version = profile_data.get("evaluation_version") or "associate_screen_v1"
    db_profile = get_screening_profile(db, founder_id, evaluation_version=evaluation_version)
    if db_profile is None and profile_data.get("external_record_id"):
        db_profile = get_screening_profile_by_external_record_id(db, profile_data["external_record_id"])

    evaluation = evaluate_recommendation(
        profile_data.get("founder_score"),
        profile_data.get("vision_product_score"),
        profile_data.get("differentiation_score"),
        profile_data.get("traction_score"),
    )

    payload = {
        "founder_id": founder_id,
        "external_record_id": profile_data.get("external_record_id"),
        "project_name": profile_data.get("project_name"),
        "project_name_normalized": normalize_text_value(profile_data.get("project_name")),
        "project_summary": profile_data.get("project_summary"),
        "founder_role": profile_data.get("founder_role"),
        "sector": profile_data.get("sector"),
        "stage": profile_data.get("stage"),
        "source_type": profile_data.get("source_type"),
        "institution_or_program": profile_data.get("institution_or_program"),
        "school_or_lab": profile_data.get("school_or_lab"),
        "cohort_year": profile_data.get("cohort_year"),
        "institution_affiliation_basis": profile_data.get("institution_affiliation_basis"),
        "city": profile_data.get("city"),
        "city_normalized": normalize_text_value(profile_data.get("city")),
        "country": profile_data.get("country"),
        "city_basis": profile_data.get("city_basis"),
        "city_confidence": profile_data.get("city_confidence"),
        "target_market_geography": profile_data.get("target_market_geography"),
        "website_url": profile_data.get("website_url"),
        "primary_source_url": profile_data.get("primary_source_url"),
        "source_locator": profile_data.get("source_locator"),
        "source_date": profile_data.get("source_date"),
        "funding_status": (
            profile_data.get("funding_status").value
            if isinstance(profile_data.get("funding_status"), ScreeningFundingStatus)
            else profile_data.get("funding_status", ScreeningFundingStatus.UNKNOWN.value)
        ),
        "funding_check_as_of": profile_data.get("funding_check_as_of"),
        "funding_check_confidence": profile_data.get("funding_check_confidence"),
        "funding_notes": profile_data.get("funding_notes"),
        "founder_score": profile_data.get("founder_score"),
        "founder_score_rationale": profile_data.get("founder_score_rationale"),
        "vision_product_score": profile_data.get("vision_product_score"),
        "vision_product_rationale": profile_data.get("vision_product_rationale"),
        "differentiation_score": profile_data.get("differentiation_score"),
        "differentiation_rationale": profile_data.get("differentiation_rationale"),
        "traction_score": profile_data.get("traction_score"),
        "traction_rationale": profile_data.get("traction_rationale"),
        "evidence_confidence": profile_data.get("evidence_confidence"),
        "evidence_coverage": profile_data.get("evidence_coverage"),
        "individual_attribution_confidence": profile_data.get("individual_attribution_confidence"),
        "evaluation_scope": profile_data.get("evaluation_scope"),
        "key_evidence": profile_data.get("key_evidence") or [],
        "counter_evidence": profile_data.get("counter_evidence") or [],
        "unknowns": profile_data.get("unknowns") or [],
        "next_diligence_action": profile_data.get("next_diligence_action"),
        "recommended": evaluation.recommended,
        "recommendation_trigger": evaluation.trigger.value,
        "recommended_reason": profile_data.get("recommended_reason") or evaluation.reason,
        "evaluation_version": evaluation_version,
        "pedigree_used_in_scoring": bool(profile_data.get("pedigree_used_in_scoring", False)),
        "import_status": profile_data.get("import_status"),
        "research_priority": profile_data.get("research_priority"),
        "tags": profile_data.get("tags") or [],
        "imported_associate_call_recommended": profile_data.get("imported_associate_call_recommended"),
        "imported_recommendation_trigger": profile_data.get("imported_recommendation_trigger"),
        "imported_recommended_reason": profile_data.get("imported_recommended_reason"),
        "produced_by": profile_data.get("produced_by"),
        "import_id": profile_data.get("import_id"),
    }

    if db_profile is None:
        db_profile = db_models.FounderScreeningProfile(
            id=f"fsp_{uuid.uuid4().hex[:12]}",
            **payload,
        )
        db.add(db_profile)
    else:
        for key, value in payload.items():
            setattr(db_profile, key, value)

    if commit:
        db.commit()
        db.refresh(db_profile)
    else:
        db.flush()
    return db_profile


def _build_founder_discovery_query(
    db: Session,
    evaluation_version: str = "associate_screen_v1",
    q: Optional[str] = None,
    recommended: Optional[bool] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    institution_or_program: Optional[str] = None,
    school_or_lab: Optional[str] = None,
    source_type: Optional[str] = None,
    sector: Optional[str] = None,
    funding_status: Optional[str] = None,
    cohort_year: Optional[str] = None,
):
    query = (
        db.query(db_models.Founder, db_models.FounderScreeningProfile)
        .outerjoin(
            db_models.FounderScreeningProfile,
            and_(
                db_models.FounderScreeningProfile.founder_id == db_models.Founder.id,
                db_models.FounderScreeningProfile.evaluation_version == evaluation_version,
            ),
        )
    )
    if recommended is True:
        query = query.filter(db_models.FounderScreeningProfile.recommended.is_(True))
    elif recommended is False:
        query = query.filter(
            or_(
                db_models.FounderScreeningProfile.id.is_(None),
                db_models.FounderScreeningProfile.recommended.is_(False),
            )
        )
    if city:
        query = query.filter(
            db_models.FounderScreeningProfile.city_normalized == normalize_text_value(city)
        )
    if country:
        query = query.filter(db_models.FounderScreeningProfile.country == country)
    if institution_or_program:
        query = query.filter(
            db_models.FounderScreeningProfile.institution_or_program == institution_or_program
        )
    if school_or_lab:
        query = query.filter(db_models.FounderScreeningProfile.school_or_lab == school_or_lab)
    if source_type:
        query = query.filter(db_models.FounderScreeningProfile.source_type == source_type)
    if sector:
        query = query.filter(db_models.FounderScreeningProfile.sector == sector)
    if funding_status:
        query = query.filter(db_models.FounderScreeningProfile.funding_status == funding_status)
    if cohort_year:
        query = query.filter(db_models.FounderScreeningProfile.cohort_year == cohort_year)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                db_models.Founder.name.ilike(pattern),
                db_models.Founder.current_company.ilike(pattern),
                db_models.Founder.role.ilike(pattern),
                db_models.Founder.source_reason.ilike(pattern),
                db_models.FounderScreeningProfile.project_name.ilike(pattern),
                db_models.FounderScreeningProfile.project_summary.ilike(pattern),
                db_models.FounderScreeningProfile.founder_role.ilike(pattern),
                cast(db_models.FounderScreeningProfile.tags, SAString).ilike(pattern),
            )
        )
    return query


def _recommended_order_columns():
    trigger_rank = case(
        (
            db_models.FounderScreeningProfile.recommendation_trigger
            == RecommendationTrigger.ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50.value,
            0,
        ),
        (
            db_models.FounderScreeningProfile.recommendation_trigger
            == RecommendationTrigger.ONE_SCORE_GT_75.value,
            1,
        ),
        (
            db_models.FounderScreeningProfile.recommendation_trigger
            == RecommendationTrigger.TWO_SCORES_GT_50.value,
            2,
        ),
        (
            db_models.FounderScreeningProfile.recommendation_trigger
            == RecommendationTrigger.NOT_RECOMMENDED.value,
            3,
        ),
        else_=4,
    )
    max_score = func.greatest(
        func.coalesce(db_models.FounderScreeningProfile.founder_score, -1),
        func.coalesce(db_models.FounderScreeningProfile.vision_product_score, -1),
        func.coalesce(db_models.FounderScreeningProfile.differentiation_score, -1),
        func.coalesce(db_models.FounderScreeningProfile.traction_score, -1),
    )
    above_50_count = (
        case((db_models.FounderScreeningProfile.founder_score > 50, 1), else_=0)
        + case((db_models.FounderScreeningProfile.vision_product_score > 50, 1), else_=0)
        + case((db_models.FounderScreeningProfile.differentiation_score > 50, 1), else_=0)
        + case((db_models.FounderScreeningProfile.traction_score > 50, 1), else_=0)
    )
    confidence_missing = case((db_models.FounderScreeningProfile.evidence_confidence.is_(None), 1), else_=0)
    coverage_missing = case((db_models.FounderScreeningProfile.evidence_coverage.is_(None), 1), else_=0)
    return [
        trigger_rank.asc(),
        max_score.desc(),
        above_50_count.desc(),
        confidence_missing.asc(),
        db_models.FounderScreeningProfile.evidence_confidence.desc(),
        coverage_missing.asc(),
        db_models.FounderScreeningProfile.evidence_coverage.desc(),
        db_models.Founder.name.asc(),
    ]


def get_founder_discovery_facets(
    db: Session,
    evaluation_version: str = "associate_screen_v1",
    q: Optional[str] = None,
    recommended: Optional[bool] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    institution_or_program: Optional[str] = None,
    school_or_lab: Optional[str] = None,
    source_type: Optional[str] = None,
    sector: Optional[str] = None,
    funding_status: Optional[str] = None,
    cohort_year: Optional[str] = None,
) -> FounderDiscoveryFacets:
    query = _build_founder_discovery_query(
        db,
        evaluation_version=evaluation_version,
        q=q,
        recommended=recommended,
        city=city,
        country=country,
        institution_or_program=institution_or_program,
        school_or_lab=school_or_lab,
        source_type=source_type,
        sector=sector,
        funding_status=funding_status,
        cohort_year=cohort_year,
    )

    def distinct_strings(column) -> List[str]:
        return [
            value
            for (value,) in query.with_entities(column)
            .filter(column.is_not(None))
            .distinct()
            .order_by(column.asc())
            .all()
            if value
        ]

    return FounderDiscoveryFacets(
        cities=distinct_strings(db_models.FounderScreeningProfile.city),
        institutions_or_programs=distinct_strings(db_models.FounderScreeningProfile.institution_or_program),
        schools_or_labs=distinct_strings(db_models.FounderScreeningProfile.school_or_lab),
        source_types=distinct_strings(db_models.FounderScreeningProfile.source_type),
        sectors=distinct_strings(db_models.FounderScreeningProfile.sector),
        funding_statuses=distinct_strings(db_models.FounderScreeningProfile.funding_status),
        cohort_years=distinct_strings(db_models.FounderScreeningProfile.cohort_year),
    )


def list_founder_discovery_items(
    db: Session,
    evaluation_version: str = "associate_screen_v1",
    q: Optional[str] = None,
    recommended: Optional[bool] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    institution_or_program: Optional[str] = None,
    school_or_lab: Optional[str] = None,
    source_type: Optional[str] = None,
    sector: Optional[str] = None,
    funding_status: Optional[str] = None,
    cohort_year: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort: Optional[str] = None,
) -> List[FounderDiscoveryItem]:
    query = _build_founder_discovery_query(
        db,
        evaluation_version=evaluation_version,
        q=q,
        recommended=recommended,
        city=city,
        country=country,
        institution_or_program=institution_or_program,
        school_or_lab=school_or_lab,
        source_type=source_type,
        sector=sector,
        funding_status=funding_status,
        cohort_year=cohort_year,
    )
    if sort == "recommended" or recommended is True:
        query = query.order_by(*_recommended_order_columns())
    else:
        query = query.order_by(desc(db_models.Founder.updated_at), db_models.Founder.name.asc())

    rows = query.offset(offset).limit(limit).all()
    founder_ids = [db_founder.id for db_founder, _ in rows]
    opportunity_map: Dict[str, OpportunityScreen] = {}
    if founder_ids:
        db_opportunities = (
            db.query(db_models.Opportunity)
            .filter(db_models.Opportunity.founder_id.in_(founder_ids))
            .order_by(db_models.Opportunity.id.asc())
            .all()
        )
        for db_opp in db_opportunities:
            opportunity_map.setdefault(
                db_opp.founder_id,
                opportunity_to_pydantic(db_opp),
            )

    return [
        FounderDiscoveryItem(
            founder=founder_to_pydantic(db, db_founder),
            profile=screening_profile_to_pydantic(db_profile) if db_profile else None,
            opportunity=opportunity_map.get(db_founder.id),
        )
        for db_founder, db_profile in rows
    ]


def count_founder_discovery_items(
    db: Session,
    evaluation_version: str = "associate_screen_v1",
    q: Optional[str] = None,
    recommended: Optional[bool] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    institution_or_program: Optional[str] = None,
    school_or_lab: Optional[str] = None,
    source_type: Optional[str] = None,
    sector: Optional[str] = None,
    funding_status: Optional[str] = None,
    cohort_year: Optional[str] = None,
) -> int:
    return _build_founder_discovery_query(
        db,
        evaluation_version=evaluation_version,
        q=q,
        recommended=recommended,
        city=city,
        country=country,
        institution_or_program=institution_or_program,
        school_or_lab=school_or_lab,
        source_type=source_type,
        sector=sector,
        funding_status=funding_status,
        cohort_year=cohort_year,
    ).count()


def get_founder_csv_import_by_checksum(
    db: Session,
    file_checksum: str,
) -> Optional[db_models.FounderCsvImport]:
    return (
        db.query(db_models.FounderCsvImport)
        .filter(db_models.FounderCsvImport.file_checksum == file_checksum)
        .order_by(db_models.FounderCsvImport.created_at.desc())
        .first()
    )


def create_founder_csv_import(
    db: Session,
    *,
    file_name: str,
    file_checksum: str,
    row_count: int,
) -> db_models.FounderCsvImport:
    db_import = db_models.FounderCsvImport(
        id=f"imp_{uuid.uuid4().hex[:12]}",
        file_name=file_name,
        file_checksum=file_checksum,
        row_count=row_count,
    )
    db.add(db_import)
    db.flush()
    return db_import


def _find_founders_by_linkedin_normalized(db: Session, linkedin_url_normalized: str) -> List[db_models.Founder]:
    return (
        db.query(db_models.Founder)
        .filter(db_models.Founder.linkedin_url_normalized == linkedin_url_normalized)
        .all()
    )


def _find_profiles_by_name_project_cohort(
    db: Session,
    founder_name_normalized: str,
    project_name_normalized: str,
    cohort_year: Optional[str],
) -> List[db_models.FounderScreeningProfile]:
    return (
        db.query(db_models.FounderScreeningProfile)
        .join(db_models.Founder, db_models.Founder.id == db_models.FounderScreeningProfile.founder_id)
        .filter(
            func.lower(func.trim(db_models.Founder.name)) == founder_name_normalized,
            db_models.FounderScreeningProfile.project_name_normalized == project_name_normalized,
            db_models.FounderScreeningProfile.cohort_year == cohort_year,
        )
        .all()
    )


def get_primary_opportunity_for_founder(
    db: Session,
    founder_id: str,
) -> Optional[db_models.Opportunity]:
    return (
        db.query(db_models.Opportunity)
        .filter(db_models.Opportunity.founder_id == founder_id)
        .order_by(db_models.Opportunity.id.asc())
        .first()
    )


def ensure_founder_opportunity(
    db: Session,
    founder_id: str,
    next_founder_action: Optional[str],
) -> db_models.Opportunity:
    db_opp = get_primary_opportunity_for_founder(db, founder_id)
    if db_opp is not None:
        if next_founder_action and not db_opp.next_founder_action:
            db_opp.next_founder_action = next_founder_action
            db.flush()
        return db_opp
    opp = db_models.Opportunity(
        id=f"opp_{uuid.uuid4().hex[:12]}",
        founder_id=founder_id,
        founder_score=0,
        founder_confidence=0,
        founder_market_fit={},
        team_completeness={},
        market_posture="neutral",
        market_confidence=0,
        idea_vs_market_posture="neutral",
        idea_vs_market_confidence=0,
        next_founder_action=next_founder_action,
        status="SCREENING",
    )
    db.add(opp)
    db.flush()
    return opp


def _resolve_import_match(
    db: Session,
    row: Dict[str, Any],
) -> tuple[Optional[db_models.Founder], Optional[db_models.FounderScreeningProfile], Optional[str]]:
    matched_founders: Dict[str, db_models.Founder] = {}
    matched_profiles: Dict[str, Optional[db_models.FounderScreeningProfile]] = {}

    external_record_id = row["external_record_id"]
    linkedin_url_normalized = row.get("linkedin_url_normalized")
    founder_name_normalized = row["founder_name_normalized"]
    project_name_normalized = row["project_name_normalized"]
    cohort_year = row.get("cohort_year")

    if external_record_id:
        db_profile = get_screening_profile_by_external_record_id(db, external_record_id)
        if db_profile is not None:
            db_founder = get_founder(db, db_profile.founder_id)
            if db_founder is not None:
                matched_founders[db_founder.id] = db_founder
                matched_profiles[db_founder.id] = db_profile

    if linkedin_url_normalized:
        linkedin_matches = _find_founders_by_linkedin_normalized(db, linkedin_url_normalized)
        if len(linkedin_matches) > 1:
            return None, None, "LinkedIn URL matches multiple founders"
        if linkedin_matches:
            db_founder = linkedin_matches[0]
            matched_founders[db_founder.id] = db_founder
            matched_profiles[db_founder.id] = get_screening_profile(db, db_founder.id, row["evaluation_version"])

    tuple_matches = _find_profiles_by_name_project_cohort(
        db,
        founder_name_normalized,
        project_name_normalized,
        cohort_year,
    )
    if len(tuple_matches) > 1:
        founder_ids = {match.founder_id for match in tuple_matches}
        if len(founder_ids) > 1:
            return None, None, "Founder/project/cohort tuple matches multiple founders"
    if tuple_matches:
        db_profile = tuple_matches[0]
        db_founder = get_founder(db, db_profile.founder_id)
        if db_founder is not None:
            matched_founders[db_founder.id] = db_founder
            matched_profiles[db_founder.id] = db_profile

    if len(matched_founders) > 1:
        return None, None, "Candidate matches disagree across external id, LinkedIn URL, and founder/project/cohort tuple"

    if not matched_founders:
        return None, None, None

    founder_id = next(iter(matched_founders.keys()))
    return matched_founders[founder_id], matched_profiles.get(founder_id), None


def bulk_upsert_founders_and_profiles(
    db: Session,
    *,
    rows: List[Dict[str, Any]],
    file_name: str,
    file_checksum: str,
    dry_run: bool = True,
    force: bool = False,
) -> CsvImportResult:
    if not dry_run and not force and get_founder_csv_import_by_checksum(db, file_checksum):
        raise ValueError("This CSV file has already been imported. Re-run with force=true to import it again.")

    errors: List[CsvImportRowError] = []
    founders_to_create = 0
    founders_to_update = 0
    profiles_to_create = 0
    profiles_to_update = 0

    matched_rows: List[Dict[str, Any]] = []
    for row in rows:
        row_errors: List[CsvImportRowError] = []
        db_founder, db_profile, conflict = _resolve_import_match(db, row)
        if conflict:
            errors.append(
                CsvImportRowError(
                    row_number=row["row_number"],
                    external_record_id=row.get("external_record_id"),
                    message=conflict,
                )
            )
            continue

        if db_founder is not None:
            if db_founder.name.strip() != row["founder_name"].strip():
                row_errors.append(
                    CsvImportRowError(
                        row_number=row["row_number"],
                        external_record_id=row.get("external_record_id"),
                        field="founder_name",
                        message="Matched founder has a different name; explicit merge is required.",
                    )
                )
            if (
                row.get("linkedin_url")
                and db_founder.linkedin_url
                and normalize_url_value(db_founder.linkedin_url) != row.get("linkedin_url_normalized")
            ):
                row_errors.append(
                    CsvImportRowError(
                        row_number=row["row_number"],
                        external_record_id=row.get("external_record_id"),
                        field="linkedin_url",
                        message="Matched founder has a different LinkedIn URL; explicit merge is required.",
                    )
                )

        if row_errors:
            errors.extend(row_errors)
            continue

        row["matched_founder"] = db_founder
        row["matched_profile"] = db_profile
        matched_rows.append(row)

        if db_founder is None:
            founders_to_create += 1
        else:
            founders_to_update += 1
        if db_profile is None:
            profiles_to_create += 1
        else:
            profiles_to_update += 1

    if errors:
        invalid_row_numbers = {error.row_number for error in errors}
        return CsvImportResult(
            dry_run=dry_run,
            file_name=file_name,
            rows_received=len(rows),
            rows_valid=len(rows) - len(invalid_row_numbers),
            rows_invalid=len(invalid_row_numbers),
            founders_to_create=founders_to_create,
            founders_to_update=founders_to_update,
            profiles_to_create=profiles_to_create,
            profiles_to_update=profiles_to_update,
            rows_skipped=0,
            errors=errors,
        )

    if dry_run:
        return CsvImportResult(
            dry_run=True,
            file_name=file_name,
            rows_received=len(rows),
            rows_valid=len(rows),
            rows_invalid=0,
            founders_to_create=founders_to_create,
            founders_to_update=founders_to_update,
            profiles_to_create=profiles_to_create,
            profiles_to_update=profiles_to_update,
            rows_skipped=0,
            errors=[],
        )

    created_founder_ids: List[str] = []
    updated_founder_ids: List[str] = []
    created_profile_ids: List[str] = []
    updated_profile_ids: List[str] = []

    db_import = create_founder_csv_import(
        db,
        file_name=file_name,
        file_checksum=file_checksum,
        row_count=len(rows),
    )

    for row in matched_rows:
        db_founder = row["matched_founder"]
        db_profile = row["matched_profile"]
        if db_founder is None:
            founder_id = f"fnd_{uuid.uuid4().hex[:12]}"
            db_founder = db_models.Founder(
                id=founder_id,
                name=row["founder_name"],
                email=create_placeholder_import_email(row.get("external_record_id"), founder_id),
                current_company=row.get("project_name"),
                role=row.get("founder_role"),
                location=row.get("founder_location"),
                location_city=row.get("city"),
                linkedin_url=row.get("linkedin_url"),
                linkedin_url_normalized=row.get("linkedin_url_normalized"),
                github_url=row.get("github_url"),
                source_reason=row.get("project_summary"),
                source_url=row.get("primary_source_url"),
                enrichment_policy=EnrichmentPolicy.MANUAL.value,
            )
            db.add(db_founder)
            db.flush()
            created_founder_ids.append(db_founder.id)
        else:
            if not db_founder.current_company and row.get("project_name"):
                db_founder.current_company = row["project_name"]
            if not db_founder.role and row.get("founder_role"):
                db_founder.role = row["founder_role"]
            if not db_founder.location_city and row.get("city"):
                db_founder.location_city = row["city"]
            if not db_founder.location and row.get("founder_location"):
                db_founder.location = row["founder_location"]
            if not db_founder.linkedin_url and row.get("linkedin_url"):
                db_founder.linkedin_url = row["linkedin_url"]
                db_founder.linkedin_url_normalized = row.get("linkedin_url_normalized")
            if not db_founder.github_url and row.get("github_url"):
                db_founder.github_url = row["github_url"]
            if not db_founder.source_url and row.get("primary_source_url"):
                db_founder.source_url = row["primary_source_url"]
            if not db_founder.source_reason and row.get("project_summary"):
                db_founder.source_reason = row["project_summary"]
            if db_founder.enrichment_policy == EnrichmentPolicy.AUTO.value:
                db_founder.enrichment_policy = EnrichmentPolicy.MANUAL.value
            db.flush()
            updated_founder_ids.append(db_founder.id)

        profile_payload = dict(row["profile_data"])
        profile_payload["import_id"] = db_import.id
        profile_payload["produced_by"] = profile_payload.get("produced_by") or "csv_import"
        saved_profile = create_or_update_screening_profile(
            db,
            db_founder.id,
            profile_payload,
            commit=False,
        )
        if db_profile is None:
            created_profile_ids.append(saved_profile.id)
        else:
            updated_profile_ids.append(saved_profile.id)

        ensure_founder_opportunity(db, db_founder.id, profile_payload.get("next_diligence_action"))

    db.commit()

    return CsvImportResult(
        dry_run=False,
        file_name=file_name,
        rows_received=len(rows),
        rows_valid=len(rows),
        rows_invalid=0,
        founders_to_create=founders_to_create,
        founders_to_update=founders_to_update,
        profiles_to_create=profiles_to_create,
        profiles_to_update=profiles_to_update,
        rows_skipped=0,
        errors=[],
        import_id=db_import.id,
        created_founder_ids=created_founder_ids,
        updated_founder_ids=updated_founder_ids,
        created_profile_ids=created_profile_ids,
        updated_profile_ids=updated_profile_ids,
    )


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


def update_thesis(db: Session, thesis_id: str, updates: Dict) -> Optional[db_models.Thesis]:
    db_thesis = get_thesis(db, thesis_id)
    if not db_thesis:
        return None
    for key, value in updates.items():
        setattr(db_thesis, key, value)
    db.commit()
    db.refresh(db_thesis)
    return db_thesis


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
        source=item.source,
        reason=item.reason,
        thesis_id=item.thesis_id,
        job_id=item.job_id,
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
        source=db_item.source,
        reason=db_item.reason,
        thesis_id=db_item.thesis_id,
        job_id=db_item.job_id,
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


def list_pool_items(db: Session, status: Optional[str] = None, job_id: Optional[str] = None) -> List[db_models.FounderPoolItem]:
    query = db.query(db_models.FounderPoolItem)
    if status:
        query = query.filter(db_models.FounderPoolItem.status == status)
    if job_id:
        query = query.filter(db_models.FounderPoolItem.job_id == job_id)
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
        status=opp.status,
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
        status=db_opp.status,
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
        # Preserve the persisted case status; status is managed via the
        # dedicated status endpoint, not via opportunity screen updates.
    else:
        db_opp = opportunity_to_db(opp)
        db.add(db_opp)
    db.commit()
    db.refresh(db_opp)
    return db_opp


def update_opportunity_status(db: Session, opportunity_id: str, status: str) -> Optional[db_models.Opportunity]:
    db_opp = get_opportunity(db, opportunity_id)
    if not db_opp:
        return None
    db_opp.status = status
    db.commit()
    db.refresh(db_opp)
    return db_opp


def get_opportunity(db: Session, opportunity_id: str) -> Optional[db_models.Opportunity]:
    return db.query(db_models.Opportunity).filter(db_models.Opportunity.id == opportunity_id).first()


def list_opportunities(
    db: Session,
    founder_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[db_models.Opportunity]:
    query = db.query(db_models.Opportunity)
    if founder_id:
        query = query.filter(db_models.Opportunity.founder_id == founder_id)
    if status:
        query = query.filter(db_models.Opportunity.status == status)
    return query.order_by(db_models.Opportunity.id).all()


# -----------------------------------------------------------------------------
# Claims
# -----------------------------------------------------------------------------

def claim_to_db(claim: Claim) -> db_models.Claim:
    return db_models.Claim(
        id=claim.id,
        opportunity_id=claim.opportunity_id,
        founder_id=claim.founder_id,
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
        founder_id=db_claim.founder_id,
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


def list_claims_for_founder(db: Session, founder_id: str) -> List[Claim]:
    db_claims = (
        db.query(db_models.Claim)
        .filter(db_models.Claim.founder_id == founder_id)
        .all()
    )
    return [claim_to_pydantic(c) for c in db_claims]


# -----------------------------------------------------------------------------
# Sourcing Schedules
# -----------------------------------------------------------------------------

def sourcing_schedule_to_db(schedule: SourcingSchedule) -> db_models.SourcingSchedule:
    return db_models.SourcingSchedule(
        id=schedule.id,
        thesis_id=schedule.thesis_id,
        enabled=schedule.enabled,
        interval_seconds=schedule.interval_seconds,
        max_leads_per_run=schedule.max_leads_per_run,
        sources=[s.model_dump(mode="json") for s in schedule.sources] if schedule.sources else [],
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def sourcing_schedule_to_pydantic(db_schedule: db_models.SourcingSchedule) -> SourcingSchedule:
    from models import SourceConfig

    return SourcingSchedule(
        id=db_schedule.id,
        thesis_id=db_schedule.thesis_id,
        enabled=db_schedule.enabled,
        interval_seconds=db_schedule.interval_seconds,
        max_leads_per_run=db_schedule.max_leads_per_run,
        sources=[SourceConfig(**s) for s in db_schedule.sources] if db_schedule.sources else [],
        last_run_at=db_schedule.last_run_at,
        next_run_at=db_schedule.next_run_at,
        created_at=db_schedule.created_at,
        updated_at=db_schedule.updated_at,
    )


def create_sourcing_schedule(db: Session, schedule: SourcingSchedule) -> db_models.SourcingSchedule:
    db_schedule = sourcing_schedule_to_db(schedule)
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def get_sourcing_schedule(db: Session, schedule_id: str) -> Optional[db_models.SourcingSchedule]:
    return db.query(db_models.SourcingSchedule).filter(db_models.SourcingSchedule.id == schedule_id).first()


def get_sourcing_schedule_by_thesis(db: Session, thesis_id: str) -> Optional[db_models.SourcingSchedule]:
    return (
        db.query(db_models.SourcingSchedule)
        .filter(db_models.SourcingSchedule.thesis_id == thesis_id)
        .first()
    )


def list_sourcing_schedules(db: Session, enabled_only: bool = False) -> List[db_models.SourcingSchedule]:
    query = db.query(db_models.SourcingSchedule)
    if enabled_only:
        query = query.filter(db_models.SourcingSchedule.enabled == True)
    return query.order_by(db_models.SourcingSchedule.created_at.desc()).all()


def update_sourcing_schedule(
    db: Session, schedule_id: str, updates: Dict
) -> Optional[db_models.SourcingSchedule]:
    db_schedule = get_sourcing_schedule(db, schedule_id)
    if not db_schedule:
        return None
    for key, value in updates.items():
        setattr(db_schedule, key, value)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def delete_sourcing_schedule(db: Session, schedule_id: str) -> bool:
    db_schedule = get_sourcing_schedule(db, schedule_id)
    if not db_schedule:
        return False
    db.delete(db_schedule)
    db.commit()
    return True


def list_due_sourcing_schedules(db: Session, now: Optional[datetime] = None) -> List[db_models.SourcingSchedule]:
    now = now or datetime.now(timezone.utc)
    return (
        db.query(db_models.SourcingSchedule)
        .filter(db_models.SourcingSchedule.enabled == True)
        .filter(
            (db_models.SourcingSchedule.next_run_at == None)  # noqa: E711
            | (db_models.SourcingSchedule.next_run_at <= now)
        )
        .all()
    )


# -----------------------------------------------------------------------------
# Sourcing Jobs
# -----------------------------------------------------------------------------

def sourcing_job_to_db(job: SourcingJob) -> db_models.SourcingJob:
    return db_models.SourcingJob(
        id=job.id,
        thesis_id=job.thesis_id,
        schedule_id=job.schedule_id,
        status=job.status,
        progress=job.progress,
        started_at=job.started_at,
        ended_at=job.ended_at,
        leads_found=job.leads_found,
        leads_added=job.leads_added,
        leads_skipped=job.leads_skipped,
        result=job.result,
        error_message=job.error_message,
        created_at=job.created_at,
    )


def sourcing_job_to_pydantic(db_job: db_models.SourcingJob) -> SourcingJob:
    return SourcingJob(
        id=db_job.id,
        thesis_id=db_job.thesis_id,
        schedule_id=db_job.schedule_id,
        status=db_job.status,
        progress=db_job.progress,
        started_at=db_job.started_at,
        ended_at=db_job.ended_at,
        leads_found=db_job.leads_found,
        leads_added=db_job.leads_added,
        leads_skipped=db_job.leads_skipped,
        result=db_job.result,
        error_message=db_job.error_message,
        created_at=db_job.created_at,
    )


def create_sourcing_job(db: Session, job: SourcingJob) -> db_models.SourcingJob:
    db_job = sourcing_job_to_db(job)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def get_sourcing_job(db: Session, job_id: str) -> Optional[db_models.SourcingJob]:
    return db.query(db_models.SourcingJob).filter(db_models.SourcingJob.id == job_id).first()


def list_sourcing_jobs(
    db: Session,
    thesis_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[db_models.SourcingJob]:
    query = db.query(db_models.SourcingJob)
    if thesis_id:
        query = query.filter(db_models.SourcingJob.thesis_id == thesis_id)
    if status:
        query = query.filter(db_models.SourcingJob.status == status)
    return query.order_by(db_models.SourcingJob.created_at.desc()).limit(limit).all()


def update_sourcing_job(db: Session, job_id: str, updates: Dict) -> Optional[db_models.SourcingJob]:
    db_job = get_sourcing_job(db, job_id)
    if not db_job:
        return None
    for key, value in updates.items():
        setattr(db_job, key, value)
    db.commit()
    db.refresh(db_job)
    return db_job


# -----------------------------------------------------------------------------
# Enrichment
# -----------------------------------------------------------------------------

def list_founders_below_confidence(
    db: Session,
    threshold: float,
    max_results: int,
    min_gap_seconds: int,
    never_enriched_only: bool = False,
) -> List[db_models.Founder]:
    """Return founders whose latest snapshot confidence is below `threshold`
    and that have not been enriched within `min_gap_seconds`.

    Cold-start founders (no snapshot yet, i.e. 0% confidence) are included.
    Ordered by confidence ASC so the weakest founders are enriched first.

    When `never_enriched_only` is True, only founders that have never completed
    an enrichment pass (``enrichment_attempts == 0``) are returned. This enforces
    the "enrich once" rule: each founder is enriched exactly once.
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=min_gap_seconds)
    founders = (
        db.query(db_models.Founder)
        .outerjoin(
            db_models.ScoreSnapshot,
            db_models.ScoreSnapshot.id == db_models.Founder.latest_score_snapshot_id,
        )
        .all()
    )
    candidates = []
    for f in founders:
        if f.enrichment_policy != EnrichmentPolicy.AUTO.value:
            continue
        if never_enriched_only and f.enrichment_attempts > 0:
            continue
        snapshot = (
            db.query(db_models.ScoreSnapshot)
            .filter(db_models.ScoreSnapshot.id == f.latest_score_snapshot_id)
            .first()
            if f.latest_score_snapshot_id
            else None
        )
        confidence = snapshot.overall_confidence if snapshot else 0.0
        if confidence >= threshold:
            continue
        # When enriching once-only, debounce in-flight founders via last_enriched_at
        # so the same founder isn't re-queued before its chain completes.
        if f.last_enriched_at is not None and f.last_enriched_at > cutoff:
            continue
        candidates.append((confidence, f))

    candidates.sort(key=lambda pair: pair[0])
    return [f for _, f in candidates[:max_results]]


def count_founders_blocking_sourcing(db: Session, threshold: float) -> int:
    """Count founders that should keep automatic sourcing paused.

    A founder blocks sourcing while it is below the confidence threshold AND
    has not yet completed an enrichment pass (``enrichment_attempts == 0``).
    Once a founder has been enriched once it stops blocking, even if its
    confidence is still below threshold — matching the "enrich once" rule.
    In-flight enrichments (queued but not completed) keep blocking until the
    chain finishes and increments ``enrichment_attempts``.
    """
    founders = db.query(db_models.Founder).all()
    count = 0
    for f in founders:
        if f.enrichment_policy != EnrichmentPolicy.AUTO.value:
            continue
        if f.enrichment_attempts > 0:
            continue
        snapshot = (
            db.query(db_models.ScoreSnapshot)
            .filter(db_models.ScoreSnapshot.id == f.latest_score_snapshot_id)
            .first()
            if f.latest_score_snapshot_id
            else None
        )
        confidence = snapshot.overall_confidence if snapshot else 0.0
        if confidence < threshold:
            count += 1
    return count


def increment_enrichment_attempts(db: Session, founder_id: str) -> None:
    db_founder = get_founder(db, founder_id)
    if not db_founder:
        return
    db_founder.enrichment_attempts = (db_founder.enrichment_attempts or 0) + 1
    db.commit()


def mark_founder_enriched(db: Session, founder_id: str, enriched_at: Optional[datetime] = None) -> None:
    db_founder = get_founder(db, founder_id)
    if not db_founder:
        return
    db_founder.last_enriched_at = enriched_at or datetime.now(timezone.utc)
    db.commit()


def enrichment_run_to_db(run: EnrichmentRun) -> db_models.EnrichmentRun:
    return db_models.EnrichmentRun(
        id=run.id,
        founder_id=run.founder_id,
        stage=run.stage,
        status=run.status,
        evidence_added=run.evidence_added,
        confidence_before=run.confidence_before,
        confidence_after=run.confidence_after,
        started_at=run.started_at,
        ended_at=run.ended_at,
        error_message=run.error_message,
    )


def enrichment_run_to_pydantic(db_run: db_models.EnrichmentRun) -> EnrichmentRun:
    return EnrichmentRun(
        id=db_run.id,
        founder_id=db_run.founder_id,
        stage=db_run.stage,
        status=db_run.status,
        evidence_added=db_run.evidence_added,
        confidence_before=db_run.confidence_before,
        confidence_after=db_run.confidence_after,
        started_at=db_run.started_at,
        ended_at=db_run.ended_at,
        error_message=db_run.error_message,
        created_at=db_run.created_at,
    )


def create_enrichment_run(db: Session, run: EnrichmentRun) -> db_models.EnrichmentRun:
    db_run = enrichment_run_to_db(run)
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


def update_enrichment_run(db: Session, run_id: str, updates: Dict) -> Optional[db_models.EnrichmentRun]:
    db_run = db.query(db_models.EnrichmentRun).filter(db_models.EnrichmentRun.id == run_id).first()
    if not db_run:
        return None
    for key, value in updates.items():
        setattr(db_run, key, value)
    db.commit()
    db.refresh(db_run)
    return db_run


def list_enrichment_runs(
    db: Session,
    founder_id: Optional[str] = None,
    limit: int = 50,
) -> List[db_models.EnrichmentRun]:
    query = db.query(db_models.EnrichmentRun)
    if founder_id:
        query = query.filter(db_models.EnrichmentRun.founder_id == founder_id)
    return query.order_by(db_models.EnrichmentRun.created_at.desc()).limit(limit).all()
