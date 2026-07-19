from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float
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
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_research_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_research_sources: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    social_background_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latest_score_snapshot_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    evidence_items: Mapped[List["EvidenceItem"]] = relationship(back_populates="founder")
    score_snapshots: Mapped[List["ScoreSnapshot"]] = relationship(back_populates="founder")
    social_backgrounds: Mapped[List["SocialMediaBackground"]] = relationship(back_populates="founder")


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
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
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
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    leads_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
