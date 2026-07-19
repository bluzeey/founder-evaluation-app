from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    VERIFIED_OUTCOME = "verified_outcome"
    WORK_SAMPLE = "work_sample"
    REPEATED_BEHAVIOR = "repeated_behavior"
    INSPECTED_ARTIFACT = "inspected_artifact"
    STRUCTURED_SIMULATION = "structured_simulation"
    STRUCTURED_INTERVIEW = "structured_interview"
    SELF_REPORTED = "self_reported"
    UNVERIFIED_PROXY = "unverified_proxy"
    PRESTIGE_PROXY = "prestige_proxy"
    INFERRED_ESTIMATE = "inferred_estimate"


class EvidenceStatus(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    CONTRADICTORY = "contradictory"
    UNKNOWN = "unknown"


class Dimension(str, Enum):
    EXECUTION_AND_SHIPPING = "execution_and_shipping"
    TECHNICAL_OR_DOMAIN_ABILITY = "technical_or_domain_ability"
    AGENCY_AND_INITIATIVE = "agency_and_initiative"
    LEARNING_VELOCITY = "learning_velocity"
    RESILIENCE_AND_PERSISTENCE = "resilience_and_persistence"
    COMMERCIAL_RECRUITING_DISTRIBUTION_ABILITY = "commercial_recruiting_distribution_ability"
    COLLABORATION_AND_INTEGRITY = "collaboration_and_integrity"
    PRIOR_VENTURE_OUTCOMES = "prior_venture_outcomes"


DIMENSION_WEIGHTS = {
    Dimension.EXECUTION_AND_SHIPPING: 0.20,
    Dimension.TECHNICAL_OR_DOMAIN_ABILITY: 0.18,
    Dimension.AGENCY_AND_INITIATIVE: 0.15,
    Dimension.LEARNING_VELOCITY: 0.12,
    Dimension.RESILIENCE_AND_PERSISTENCE: 0.10,
    Dimension.COMMERCIAL_RECRUITING_DISTRIBUTION_ABILITY: 0.10,
    Dimension.COLLABORATION_AND_INTEGRITY: 0.10,
    Dimension.PRIOR_VENTURE_OUTCOMES: 0.05,
}

EVIDENCE_TYPE_STRENGTH = {
    EvidenceType.VERIFIED_OUTCOME: 1.00,
    EvidenceType.WORK_SAMPLE: 0.85,
    EvidenceType.REPEATED_BEHAVIOR: 0.80,
    EvidenceType.INSPECTED_ARTIFACT: 0.75,
    EvidenceType.STRUCTURED_SIMULATION: 0.60,
    EvidenceType.STRUCTURED_INTERVIEW: 0.45,
    EvidenceType.SELF_REPORTED: 0.25,
    EvidenceType.INFERRED_ESTIMATE: 0.25,
    EvidenceType.UNVERIFIED_PROXY: 0.0,
    EvidenceType.PRESTIGE_PROXY: 0.0,
}

REQUIRED_EFFECTIVE_WEIGHT = 1.5


class EvidenceItem(BaseModel):
    id: str
    founder_id: str
    dimension: Dimension
    observation: str
    source_type: str
    source_id: str
    source_locator: str
    evidence_type: EvidenceType
    rubric_level: int = Field(..., ge=0, le=4)
    source_trust: float = Field(..., ge=0.0, le=1.0)
    task_relevance: float = Field(..., ge=0.0, le=1.0)
    recency_factor: float = Field(..., ge=0.0, le=1.0)
    independence_group: str
    polarity: EvidenceStatus
    status: EvidenceStatus
    counter_evidence: Optional[str] = None
    unknowns: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DimensionBreakdown(BaseModel):
    dimension: Dimension
    weight: float
    raw_score: float
    adjusted_score: float
    confidence: float
    evidence_band_low: float
    evidence_band_high: float
    coverage: float
    evidence_count: int
    contradiction_count: int
    unknown: bool
    positive_evidence: List[str]
    counter_evidence: List[str]
    unknowns: List[str]
    next_test: Optional[str] = None


class ScoreSnapshot(BaseModel):
    id: str
    founder_id: str
    rubric_version: str
    prompt_version: str
    model_version: str
    created_at: datetime
    founder_score: float
    evidence_band_low: float
    evidence_band_high: float
    overall_confidence: float
    evidence_coverage: float
    trend: int
    dimension_breakdowns: List[DimensionBreakdown]
    evidence_items: List[EvidenceItem]
    change_explanation: Optional[str] = None


class FounderMarketFit(BaseModel):
    domain_knowledge: Optional[float] = None
    customer_access: Optional[float] = None
    unique_insight: Optional[float] = None
    personal_motivation: Optional[float] = None
    problem_proximity: Optional[float] = None
    technical_operational_advantage: Optional[float] = None
    score: Optional[float] = None
    confidence: float = 0.0
    coverage: float = 0.0


class TeamCompleteness(BaseModel):
    complementary_skills: Optional[float] = None
    missing_critical_roles: List[str] = []
    co_founder_alignment: Optional[float] = None
    decision_rights: Optional[float] = None
    commitment_availability: Optional[float] = None
    score: Optional[float] = None
    confidence: float = 0.0
    coverage: float = 0.0


class OpportunityScreen(BaseModel):
    opportunity_id: str
    founder_id: str
    founder_score: float
    founder_confidence: float
    founder_market_fit: FounderMarketFit
    team_completeness: TeamCompleteness
    market_posture: str = "neutral"
    market_confidence: float = 0.0
    idea_vs_market_posture: str = "neutral"
    idea_vs_market_confidence: float = 0.0
    next_founder_action: Optional[str] = None


class TrustStatus(str, Enum):
    VERIFIED = "verified"
    SUPPORTED = "supported"
    FOUNDER_REPORTED = "founder_reported"
    INFERRED = "inferred"
    CONTRADICTED = "contradicted"
    MISSING = "missing"
    STALE = "stale"


class Claim(BaseModel):
    id: str
    opportunity_id: str
    founder_id: Optional[str] = None
    claim: str
    source: str
    trust_status: TrustStatus
    confidence: float
    contradiction: Optional[str] = None
    owner: Optional[str] = None
    next_action: Optional[str] = None


class SourceConfig(BaseModel):
    platform: str = "linkedin"  # linkedin, twitter, other
    keywords: str = ""


class SourcingSchedule(BaseModel):
    id: str
    thesis_id: str
    enabled: bool = True
    interval_seconds: int = 3600
    max_leads_per_run: int = 10
    sources: List[SourceConfig] = []
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourcingJob(BaseModel):
    id: str
    thesis_id: str
    schedule_id: Optional[str] = None
    status: str = "pending"
    progress: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    leads_found: int = 0
    leads_added: int = 0
    leads_skipped: int = 0
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SocialFootprint(BaseModel):
    platform: str
    url: str
    snippet: Optional[str] = None
    source_trust: float = Field(0.5, ge=0.0, le=1.0)


class SocialMediaBackground(BaseModel):
    id: str
    founder_id: str
    status: str = "pending"  # pending | running | completed | failed
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    summary: Optional[str] = None
    footprints: List[SocialFootprint] = []
    evidence_items: List[EvidenceItem] = []
    score_snapshot: Optional[ScoreSnapshot] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PoolItemStatus(str, Enum):
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    DISMISSED = "dismissed"


class FounderPoolItem(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    current_company: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    source_url: Optional[str] = None
    source: Optional[str] = None
    reason: str
    thesis_id: Optional[str] = None
    job_id: Optional[str] = None
    status: PoolItemStatus = PoolItemStatus.RECOMMENDED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssessmentModule(str, Enum):
    PROBLEM_FRAMING = "problem_framing"
    SALES_OBJECTION = "sales_objection"
    PRIORITIZATION = "prioritization"
    BELIEF_UPDATING = "belief_updating"
    SCALING_LEADERSHIP = "scaling_leadership"
    SETBACK_OWNERSHIP = "setback_ownership"
    CLAIM_CALIBRATION = "claim_calibration"
    ROLE_WORK_SAMPLE = "role_work_sample"


class GraderOutput(BaseModel):
    dimension: Dimension
    rubric_version: str
    rubric_level: int
    score: float
    confidence: float
    evidence: List[Dict[str, Any]]
    counter_evidence: List[Dict[str, Any]]
    unknowns: List[str]
    next_test: Optional[str] = None


class AssessmentSession(BaseModel):
    id: str
    founder_id: str
    modules: List[AssessmentModule]
    status: str = "pending"
    transcript: List[Dict[str, Any]] = []
    grader_a_outputs: List[GraderOutput] = []
    grader_b_outputs: List[GraderOutput] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Thesis(BaseModel):
    id: str
    name: str
    sectors: List[str]
    stages: List[str]
    geographies: List[str]
    check_size_min: float
    check_size_max: float
    risk_appetite: str
    min_evidence_requirements: Dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Founder(BaseModel):
    id: str
    name: str
    email: str
    current_company: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    location_city: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    source_reason: Optional[str] = None
    source_url: Optional[str] = None
    ai_research_summary: Optional[str] = None
    ai_research_sources: List[str] = []
    social_background_id: Optional[str] = None
    latest_score_snapshot: Optional[ScoreSnapshot] = None


class ApprovedPoolItemResponse(BaseModel):
    founder: Founder
    opportunity_id: str


class Decision(str, Enum):
    ADVANCE = "advance"
    DILIGENCE = "diligence"
    HOLD = "hold"
    DECLINE = "decline"
