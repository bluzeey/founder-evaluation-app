from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Founder(Base):
    __tablename__ = "founders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    current_company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linkedin_url_normalized: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_research_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_research_sources: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    social_background_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latest_score_snapshot_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    enrichment_policy: Mapped[str] = mapped_column(String, nullable=False, default="AUTO", server_default="AUTO", index=True)
    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    evidence_items: Mapped[List["EvidenceItem"]] = relationship(back_populates="founder")
    score_snapshots: Mapped[List["ScoreSnapshot"]] = relationship(back_populates="founder")
    social_backgrounds: Mapped[List["SocialMediaBackground"]] = relationship(back_populates="founder")
    screening_profiles: Mapped[List["FounderScreeningProfile"]] = relationship(
        back_populates="founder",
        cascade="all, delete-orphan",
    )


class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sectors: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    stages: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    geographies: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    check_size_min: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    check_size_max: Mapped[float] = mapped_column(Float, nullable=False, default=1_000_000)
    risk_appetite: Mapped[str] = mapped_column(String, nullable=False, default="moderate")
    min_evidence_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    founder_id: Mapped[str] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String, nullable=False, index=True)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_locator: Mapped[str] = mapped_column(String, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    rubric_level: Mapped[int] = mapped_column(Integer, nullable=False)
    source_trust: Mapped[float] = mapped_column(Float, nullable=False)
    task_relevance: Mapped[float] = mapped_column(Float, nullable=False)
    recency_factor: Mapped[float] = mapped_column(Float, nullable=False)
    independence_group: Mapped[str] = mapped_column(String, nullable=False)
    polarity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    counter_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unknowns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)

    founder: Mapped["Founder"] = relationship(back_populates="evidence_items")


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    founder_id: Mapped[str] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=False, index=True)
    rubric_version: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    founder_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_band_low: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_band_high: Mapped[float] = mapped_column(Float, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dimension_breakdowns: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_items: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    change_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    founder: Mapped["Founder"] = relationship(back_populates="score_snapshots")


class SocialMediaBackground(Base):
    __tablename__ = "social_media_backgrounds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    founder_id: Mapped[str] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    footprints: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_items: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    score_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    founder: Mapped["Founder"] = relationship(back_populates="social_backgrounds")


class FounderCsvImport(Base):
    __tablename__ = "founder_csv_imports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_checksum: Mapped[str] = mapped_column(String, nullable=False, index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class FounderScreeningProfile(Base):
    __tablename__ = "founder_screening_profiles"
    __table_args__ = (
        UniqueConstraint("founder_id", "evaluation_version", name="uq_founder_screening_profile_founder_version"),
        CheckConstraint("founder_score IS NULL OR founder_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_founder_score"),
        CheckConstraint("vision_product_score IS NULL OR vision_product_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_vision_product_score"),
        CheckConstraint("differentiation_score IS NULL OR differentiation_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_differentiation_score"),
        CheckConstraint("traction_score IS NULL OR traction_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_traction_score"),
        CheckConstraint("city_confidence IS NULL OR (city_confidence >= 0 AND city_confidence <= 1)", name="ck_founder_screening_profiles_city_confidence"),
        CheckConstraint("funding_check_confidence IS NULL OR (funding_check_confidence >= 0 AND funding_check_confidence <= 1)", name="ck_founder_screening_profiles_funding_check_confidence"),
        CheckConstraint("evidence_confidence IS NULL OR (evidence_confidence >= 0 AND evidence_confidence <= 1)", name="ck_founder_screening_profiles_evidence_confidence"),
        CheckConstraint("evidence_coverage IS NULL OR (evidence_coverage >= 0 AND evidence_coverage <= 1)", name="ck_founder_screening_profiles_evidence_coverage"),
        CheckConstraint("individual_attribution_confidence IS NULL OR (individual_attribution_confidence >= 0 AND individual_attribution_confidence <= 1)", name="ck_founder_screening_profiles_individual_attribution_confidence"),
        Index(
            "ix_founder_screening_profiles_external_record_id_unique",
            "external_record_id",
            unique=True,
            postgresql_where=text("external_record_id IS NOT NULL"),
        ),
        Index("ix_founder_screening_profiles_recommended_city", "recommended", "city_normalized"),
        Index("ix_founder_screening_profiles_recommended_institution", "recommended", "institution_or_program"),
        Index("ix_founder_screening_profiles_source_type", "source_type"),
        Index("ix_founder_screening_profiles_sector", "sector"),
        Index("ix_founder_screening_profiles_funding_status", "funding_status"),
        Index("ix_founder_screening_profiles_cohort_year", "cohort_year"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    founder_id: Mapped[str] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=False, index=True)
    external_record_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    project_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    project_name_normalized: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    project_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    founder_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    institution_or_program: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    school_or_lab: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cohort_year: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    institution_affiliation_basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_normalized: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_basis: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_market_geography: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    primary_source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_locator: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    funding_status: Mapped[str] = mapped_column(String, nullable=False, default="unknown", server_default="unknown")
    funding_check_as_of: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    funding_check_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    founder_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    founder_score_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_product_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vision_product_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    differentiation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    differentiation_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traction_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    traction_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    individual_attribution_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluation_scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_evidence: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    counter_evidence: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    unknowns: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    next_diligence_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    recommendation_trigger: Mapped[str] = mapped_column(String, nullable=False, default="INCOMPLETE_EVALUATION", server_default="INCOMPLETE_EVALUATION", index=True)
    recommended_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluation_version: Mapped[str] = mapped_column(String, nullable=False, default="associate_screen_v1", server_default="associate_screen_v1", index=True)
    pedigree_used_in_scoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    import_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    research_priority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    imported_associate_call_recommended: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    imported_recommendation_trigger: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    imported_recommended_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    produced_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    import_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("founder_csv_imports.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now)

    founder: Mapped["Founder"] = relationship(back_populates="screening_profiles")


class FounderPoolItem(Base):
    __tablename__ = "founder_pool_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="recommended", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    founder_id: Mapped[str] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=False, index=True)
    founder_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    founder_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    founder_market_fit: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    team_completeness: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    market_posture: Mapped[str] = mapped_column(String, nullable=False, default="neutral")
    market_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    idea_vs_market_posture: Mapped[str] = mapped_column(String, nullable=False, default="neutral")
    idea_vs_market_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    next_founder_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="SCREENING", index=True)

    founder: Mapped["Founder"] = relationship()


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    founder_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=True, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    trust_status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SourcingSchedule(Base):
    __tablename__ = "sourcing_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    thesis_id: Mapped[str] = mapped_column(String, ForeignKey("theses.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    max_leads_per_run: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    sources: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class SourcingJob(Base):
    __tablename__ = "sourcing_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    thesis_id: Mapped[str] = mapped_column(String, ForeignKey("theses.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("sourcing_schedules.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    leads_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    founder_id: Mapped[str] = mapped_column(String, ForeignKey("founders.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    evidence_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)
