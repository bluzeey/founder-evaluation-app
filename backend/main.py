import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from logger_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

from models import (
    Founder,
    Thesis,
    EvidenceItem,
    Dimension,
    EvidenceType,
    EvidenceStatus,
    ScoreSnapshot,
    OpportunityScreen,
    FounderMarketFit,
    TeamCompleteness,
    Claim,
    TrustStatus,
    AssessmentModule,
    GraderOutput,
    Decision,
    SocialMediaBackground,
    FounderPoolItem,
    PoolItemStatus,
)
from scoring import calculate_founder_score
from research import UmansClient, create_founder_from_research, evidence_from_llm
from tasks.social_research import (
    research_social_background,
    load_social_background,
    store_social_background,
)
from tasks.founder_pool import (
    refresh_pool_task,
    load_founder_pool,
    save_founder_pool,
)

app = FastAPI(title="FounderOS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory demo store
FOUNDERS: Dict[str, Founder] = {}
THESES: Dict[str, Thesis] = {}
EVIDENCE: Dict[str, List[EvidenceItem]] = {}
ASSESSMENTS: Dict[str, Any] = {}
OPPORTUNITIES: Dict[str, OpportunityScreen] = {}
CLAIMS: Dict[str, List[Claim]] = {}


class CreateFounderRequest(BaseModel):
    name: str
    email: str
    current_company: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    auto_score: bool = True


class CreateThesisRequest(BaseModel):
    name: str
    sectors: List[str] = []
    stages: List[str] = []
    geographies: List[str] = []
    check_size_min: float = 0
    check_size_max: float = 1_000_000
    risk_appetite: str = "moderate"
    min_evidence_requirements: Optional[Dict[str, Any]] = None


class AddEvidenceRequest(BaseModel):
    items: List[EvidenceItem]


class SimulateAssessmentRequest(BaseModel):
    founder_id: str
    modules: List[AssessmentModule]
    responses: Dict[AssessmentModule, str]


class ResearchFounderRequest(BaseModel):
    query: str
    channels: List[str] = ["linkedin", "twitter", "github", "news", "company_blog"]
    auto_score: bool = True


@app.get("/health")
def health():
    logger.info("endpoint.health.ok")
    return {"status": "ok"}


@app.post("/v1/founders", response_model=Founder)
def create_founder(req: CreateFounderRequest):
    founder_id = f"fnd_{uuid.uuid4().hex[:8]}"
    logger.info(
        "endpoint.create_founder.start founder_id=%s name=%s company=%s",
        founder_id,
        req.name,
        req.current_company,
    )
    founder = Founder(
        id=founder_id,
        name=req.name,
        email=req.email,
        current_company=req.current_company,
        role=req.role,
        location=req.location,
        linkedin_url=req.linkedin_url,
        github_url=req.github_url,
    )
    FOUNDERS[founder_id] = founder
    EVIDENCE[founder_id] = []

    # Auto-trigger social background research via Celery.
    background_id = f"soc_{uuid.uuid4().hex[:8]}"
    founder.social_background_id = background_id
    pending = SocialMediaBackground(
        id=background_id,
        founder_id=founder_id,
        status="pending",
        linkedin_url=req.linkedin_url,
        github_url=req.github_url,
    )
    store_social_background(pending)
    task = research_social_background.delay(
        founder_id=founder_id,
        name=req.name,
        email=req.email,
        linkedin_url=req.linkedin_url,
        github_url=req.github_url,
        auto_score=req.auto_score,
    )
    logger.info(
        "endpoint.create_founder.end founder_id=%s background_id=%s task_id=%s",
        founder_id,
        background_id,
        task.id,
    )
    return founder


def _apply_social_background(founder_id: str) -> Optional[SocialMediaBackground]:
    """Reconcile a completed social background result from Redis into memory."""
    background = load_social_background(founder_id)
    if not background:
        return None

    founder = FOUNDERS.get(founder_id)
    if not founder:
        return background

    founder.social_background_id = background.id

    if background.status == "completed" and background.evidence_items:
        existing_ids = {item.id for item in EVIDENCE.get(founder_id, [])}
        new_items = [
            item for item in background.evidence_items if item.id not in existing_ids
        ]
        if new_items:
            existing = EVIDENCE.get(founder_id, [])
            existing.extend(new_items)
            EVIDENCE[founder_id] = existing
            snapshot = calculate_founder_score(
                founder_id, existing, founder.latest_score_snapshot
            )
            founder.latest_score_snapshot = snapshot

    return background


@app.get("/v1/founders/pool", response_model=List[FounderPoolItem])
def list_founder_pool(status: Optional[str] = None):
    """List AI-sourced founder pool recommendations."""
    pool = load_founder_pool()
    logger.info("endpoint.list_founder_pool status=%s total=%s", status, len(pool))
    if status:
        try:
            target = PoolItemStatus(status)
            pool = [item for item in pool if item.status == target]
        except ValueError:
            logger.warning("endpoint.list_founder_pool.invalid_status status=%s", status)
            raise HTTPException(status_code=400, detail="Invalid status")
    return pool


@app.post("/v1/founders/pool/refresh")
def refresh_founder_pool_endpoint(thesis_id: Optional[str] = None):
    """Manually trigger the AI sourcing agent to discover new founders."""
    logger.info("endpoint.refresh_founder_pool.start thesis_id=%s", thesis_id)
    thesis = THESES.get(thesis_id) if thesis_id else None
    if thesis_id and not thesis:
        logger.warning("endpoint.refresh_founder_pool.thesis_not_found thesis_id=%s", thesis_id)
        raise HTTPException(status_code=404, detail="Thesis not found")

    task = refresh_pool_task.delay(
        sectors=thesis.sectors if thesis else None,
        stages=thesis.stages if thesis else None,
        geographies=thesis.geographies if thesis else None,
        risk_appetite=thesis.risk_appetite if thesis else "moderate",
        thesis_id=thesis_id,
    )
    logger.info(
        "endpoint.refresh_founder_pool.queued thesis_id=%s task_id=%s",
        thesis_id,
        task.id,
    )
    return {"task_id": task.id, "status": "queued"}


@app.post("/v1/founders/pool/{item_id}/approve", response_model=Founder)
def approve_pool_item(item_id: str):
    """Approve a pool recommendation and create a Founder record."""
    logger.info("endpoint.approve_pool_item.start item_id=%s", item_id)
    pool = load_founder_pool()
    item = next((p for p in pool if p.id == item_id), None)
    if not item:
        logger.warning("endpoint.approve_pool_item.not_found item_id=%s", item_id)
        raise HTTPException(status_code=404, detail="Pool item not found")
    if item.status != PoolItemStatus.RECOMMENDED:
        logger.warning(
            "endpoint.approve_pool_item.invalid_status item_id=%s status=%s",
            item_id,
            item.status.value,
        )
        raise HTTPException(status_code=400, detail="Pool item is not recommended")

    founder_id = f"fnd_{uuid.uuid4().hex[:8]}"
    founder = Founder(
        id=founder_id,
        name=item.name,
        email=item.email or f"{item.name.lower().replace(' ', '.')}@example.com",
        current_company=item.current_company,
        role=item.role,
        location=item.location,
        linkedin_url=item.linkedin_url,
        github_url=item.github_url,
    )
    FOUNDERS[founder_id] = founder
    EVIDENCE[founder_id] = []

    # Auto-trigger social background research.
    background_id = f"soc_{uuid.uuid4().hex[:8]}"
    founder.social_background_id = background_id
    pending = SocialMediaBackground(
        id=background_id,
        founder_id=founder_id,
        status="pending",
        linkedin_url=item.linkedin_url,
        github_url=item.github_url,
    )
    store_social_background(pending)
    research_social_background.delay(
        founder_id=founder_id,
        name=founder.name,
        email=founder.email,
        linkedin_url=item.linkedin_url,
        github_url=item.github_url,
        auto_score=True,
    )

    item.status = PoolItemStatus.APPROVED
    save_founder_pool(pool)
    logger.info(
        "endpoint.approve_pool_item.end item_id=%s founder_id=%s background_id=%s",
        item_id,
        founder_id,
        background_id,
    )
    return founder


@app.post("/v1/founders/pool/{item_id}/dismiss")
def dismiss_pool_item(item_id: str):
    """Dismiss a pool recommendation."""
    logger.info("endpoint.dismiss_pool_item.start item_id=%s", item_id)
    pool = load_founder_pool()
    item = next((p for p in pool if p.id == item_id), None)
    if not item:
        logger.warning("endpoint.dismiss_pool_item.not_found item_id=%s", item_id)
        raise HTTPException(status_code=404, detail="Pool item not found")
    item.status = PoolItemStatus.DISMISSED
    save_founder_pool(pool)
    logger.info("endpoint.dismiss_pool_item.end item_id=%s", item_id)
    return {"id": item_id, "status": PoolItemStatus.DISMISSED.value}



@app.post("/v1/founders/research", response_model=Founder)
def research_founder(req: ResearchFounderRequest):
    """Research a founder with Umans AI web search and create a scored profile."""
    logger.info("endpoint.research_founder.start query=%s channels=%s", req.query, req.channels)
    try:
        client = UmansClient()
    except RuntimeError as exc:
        logger.error("endpoint.research_founder.config_error error=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        result = client.research(req.query, req.channels)
    except Exception as exc:
        logger.error("endpoint.research_founder.failed query=%s error=%s", req.query, exc)
        raise HTTPException(status_code=502, detail=f"Research failed: {exc}") from exc

    profile = result.get("profile", {})
    summary = result.get("summary", "")
    sources = result.get("sources", [])
    evidence_data = result.get("evidence", [])

    founder = create_founder_from_research(profile, summary, sources)
    FOUNDERS[founder.id] = founder
    EVIDENCE[founder.id] = []

    evidence_items = [evidence_from_llm(founder.id, item) for item in evidence_data]
    if req.auto_score and evidence_items:
        EVIDENCE[founder.id] = evidence_items
        snapshot = calculate_founder_score(founder.id, evidence_items)
        founder.latest_score_snapshot = snapshot

    logger.info(
        "endpoint.research_founder.end founder_id=%s name=%s evidence_count=%s scored=%s",
        founder.id,
        founder.name,
        len(evidence_items),
        req.auto_score and len(evidence_items) > 0,
    )
    return founder


@app.get("/v1/founders/{founder_id}", response_model=Founder)
def get_founder(founder_id: str):
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.get_founder.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    _apply_social_background(founder_id)
    logger.info("endpoint.get_founder.ok founder_id=%s", founder_id)
    return FOUNDERS[founder_id]


@app.post("/v1/founders/{founder_id}/research-social")
def research_social(founder_id: str):
    """Manually re-run social background research for a founder."""
    logger.info("endpoint.research_social.start founder_id=%s", founder_id)
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.research_social.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")

    founder = FOUNDERS[founder_id]
    background_id = f"soc_{uuid.uuid4().hex[:8]}"
    founder.social_background_id = background_id
    pending = SocialMediaBackground(
        id=background_id,
        founder_id=founder_id,
        status="pending",
        linkedin_url=founder.linkedin_url,
        github_url=founder.github_url,
    )
    store_social_background(pending)
    task = research_social_background.delay(
        founder_id=founder_id,
        name=founder.name,
        email=founder.email,
        linkedin_url=founder.linkedin_url,
        github_url=founder.github_url,
        auto_score=True,
    )
    logger.info(
        "endpoint.research_social.queued founder_id=%s background_id=%s task_id=%s",
        founder_id,
        background_id,
        task.id,
    )
    return {
        "founder_id": founder_id,
        "background_id": background_id,
        "task_id": task.id,
        "status": "pending",
    }


@app.get("/v1/founders/{founder_id}/social-background", response_model=SocialMediaBackground)
def get_social_background(founder_id: str):
    """Get the latest social background research result for a founder."""
    logger.info("endpoint.get_social_background.start founder_id=%s", founder_id)
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.get_social_background.founder_not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    background = _apply_social_background(founder_id)
    if not background:
        logger.warning("endpoint.get_social_background.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Social background not found")
    logger.info(
        "endpoint.get_social_background.ok founder_id=%s background_status=%s",
        founder_id,
        background.status,
    )
    return background


@app.post("/v1/founders/{founder_id}/evidence", response_model=ScoreSnapshot)
def add_evidence(founder_id: str, req: AddEvidenceRequest):
    logger.info(
        "endpoint.add_evidence.start founder_id=%s item_count=%s",
        founder_id,
        len(req.items),
    )
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.add_evidence.founder_not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")

    previous = FOUNDERS[founder_id].latest_score_snapshot
    existing = EVIDENCE.get(founder_id, [])
    for item in req.items:
        existing.append(item)
    EVIDENCE[founder_id] = existing

    snapshot = calculate_founder_score(founder_id, existing, previous)
    FOUNDERS[founder_id].latest_score_snapshot = snapshot
    logger.info(
        "endpoint.add_evidence.end founder_id=%s founder_score=%s confidence=%s",
        founder_id,
        snapshot.founder_score,
        snapshot.overall_confidence,
    )
    return snapshot


@app.get("/v1/founders/{founder_id}/score", response_model=ScoreSnapshot)
def get_score(founder_id: str):
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.get_score.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    snapshot = FOUNDERS[founder_id].latest_score_snapshot
    if not snapshot:
        snapshot = calculate_founder_score(founder_id, EVIDENCE.get(founder_id, []))
        FOUNDERS[founder_id].latest_score_snapshot = snapshot
    logger.info(
        "endpoint.get_score.ok founder_id=%s founder_score=%s confidence=%s",
        founder_id,
        snapshot.founder_score,
        snapshot.overall_confidence,
    )
    return snapshot


@app.get("/v1/founders/{founder_id}/history", response_model=List[ScoreSnapshot])
def get_history(founder_id: str):
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.get_history.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    snapshot = FOUNDERS[founder_id].latest_score_snapshot
    logger.info(
        "endpoint.get_history.ok founder_id=%s snapshot_count=%s",
        founder_id,
        1 if snapshot else 0,
    )
    return [snapshot] if snapshot else []


@app.post("/v1/theses", response_model=Thesis)
def create_thesis(req: CreateThesisRequest):
    thesis_id = f"ths_{uuid.uuid4().hex[:8]}"
    logger.info(
        "endpoint.create_thesis.start thesis_id=%s name=%s sectors=%s stages=%s geographies=%s",
        thesis_id,
        req.name,
        req.sectors,
        req.stages,
        req.geographies,
    )
    thesis = Thesis(
        id=thesis_id,
        name=req.name,
        sectors=req.sectors,
        stages=req.stages,
        geographies=req.geographies,
        check_size_min=req.check_size_min,
        check_size_max=req.check_size_max,
        risk_appetite=req.risk_appetite,
        min_evidence_requirements=req.min_evidence_requirements or {},
    )
    THESES[thesis_id] = thesis
    logger.info("endpoint.create_thesis.end thesis_id=%s", thesis_id)
    return thesis


@app.get("/v1/theses", response_model=List[Thesis])
def list_theses():
    logger.info("endpoint.list_theses count=%s", len(THESES))
    return list(THESES.values())


@app.get("/v1/founders", response_model=List[Founder])
def list_founders():
    logger.info("endpoint.list_founders count=%s", len(FOUNDERS))
    return list(FOUNDERS.values())


@app.post("/v1/assessments/plan")
def plan_assessment(founder_id: str):
    logger.info("endpoint.plan_assessment.start founder_id=%s", founder_id)
    if founder_id not in FOUNDERS:
        logger.warning("endpoint.plan_assessment.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    snapshot = FOUNDERS[founder_id].latest_score_snapshot
    if not snapshot:
        snapshot = calculate_founder_score(founder_id, EVIDENCE.get(founder_id, []))
        FOUNDERS[founder_id].latest_score_snapshot = snapshot

    # Simple gap planner: pick modules for low-confidence / unknown dimensions.
    low_dims = [
        b.dimension
        for b in snapshot.dimension_breakdowns
        if b.unknown or b.confidence < 0.55
    ]
    module_map = {
        Dimension.EXECUTION: AssessmentModule.PRIORITIZATION,
        Dimension.LEARNING: AssessmentModule.BELIEF_UPDATING,
        Dimension.CUSTOMER_SELLING: AssessmentModule.SALES_OBJECTION,
        Dimension.JUDGMENT: AssessmentModule.PRIORITIZATION,
        Dimension.LEADERSHIP: AssessmentModule.SCALING_LEADERSHIP,
        Dimension.OWNERSHIP: AssessmentModule.SETBACK_OWNERSHIP,
        Dimension.CLAIM_RELIABILITY: AssessmentModule.CLAIM_CALIBRATION,
    }
    selected = []
    for dim in low_dims:
        mod = module_map.get(dim)
        if mod and mod not in selected:
            selected.append(mod)

    # Demo: include sales, prioritization, belief updating, scaling by default for cold-start.
    for default_mod in [
        AssessmentModule.SALES_OBJECTION,
        AssessmentModule.PRIORITIZATION,
        AssessmentModule.BELIEF_UPDATING,
        AssessmentModule.SCALING_LEADERSHIP,
    ]:
        if default_mod not in selected:
            selected.append(default_mod)

    logger.info(
        "endpoint.plan_assessment.end founder_id=%s modules=%s",
        founder_id,
        [m.value for m in selected],
    )
    return {
        "founder_id": founder_id,
        "recommended_modules": selected,
        "reason": "Cold-start or low-confidence dimensions require structured evidence.",
    }


@app.post("/v1/assessments/simulate", response_model=ScoreSnapshot)
def simulate_assessment(req: SimulateAssessmentRequest):
    logger.info(
        "endpoint.simulate_assessment.start founder_id=%s modules=%s",
        req.founder_id,
        [m.value for m in req.modules],
    )
    if req.founder_id not in FOUNDERS:
        logger.warning("endpoint.simulate_assessment.not_found founder_id=%s", req.founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")

    # Deterministic demo grader.
    now = datetime.utcnow().isoformat()
    new_evidence = []
    module_dim_map = {
        AssessmentModule.SALES_OBJECTION: Dimension.CUSTOMER_SELLING,
        AssessmentModule.PRIORITIZATION: Dimension.JUDGMENT,
        AssessmentModule.BELIEF_UPDATING: Dimension.LEARNING,
        AssessmentModule.SCALING_LEADERSHIP: Dimension.LEADERSHIP,
        AssessmentModule.SETBACK_OWNERSHIP: Dimension.OWNERSHIP,
        AssessmentModule.CLAIM_CALIBRATION: Dimension.CLAIM_RELIABILITY,
    }
    # Demo: score each module response as strong (3) by default.
    for module, response in req.responses.items():
        dim = module_dim_map.get(module, Dimension.EXECUTION)
        item = EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            founder_id=req.founder_id,
            dimension=dim,
            observation=f"[{module.value}] {response[:120]}",
            source_type="assessment_transcript",
            source_id=f"asm_{uuid.uuid4().hex[:8]}",
            source_locator=f"module={module.value}",
            evidence_type=EvidenceType.STRUCTURED_SIMULATION,
            rubric_level=3,
            source_trust=0.7,
            task_relevance=0.9,
            recency_factor=1.0,
            independence_group=f"assessment_{now}",
            polarity=EvidenceStatus.POSITIVE,
            status=EvidenceStatus.POSITIVE,
            unknowns=f"Real-world validation still required for {module.value}.",
        )
        new_evidence.append(item)

    previous = FOUNDERS[req.founder_id].latest_score_snapshot
    existing = EVIDENCE.get(req.founder_id, [])
    existing.extend(new_evidence)
    EVIDENCE[req.founder_id] = existing

    snapshot = calculate_founder_score(req.founder_id, existing, previous)
    FOUNDERS[req.founder_id].latest_score_snapshot = snapshot
    logger.info(
        "endpoint.simulate_assessment.end founder_id=%s founder_score=%s confidence=%s",
        req.founder_id,
        snapshot.founder_score,
        snapshot.overall_confidence,
    )
    return snapshot


@app.post("/v1/opportunities/{opportunity_id}/screen", response_model=OpportunityScreen)
def screen_opportunity(opportunity_id: str):
    logger.info("endpoint.screen_opportunity.start opportunity_id=%s", opportunity_id)
    # Always recalculate from the current founder snapshot for this demo.
    opp = OPPORTUNITIES.get(opportunity_id)
    if opp:
        snapshot = FOUNDERS[opp.founder_id].latest_score_snapshot
        if not snapshot:
            snapshot = calculate_founder_score(opp.founder_id, EVIDENCE.get(opp.founder_id, []))
            FOUNDERS[opp.founder_id].latest_score_snapshot = snapshot
        opp.founder_score = snapshot.founder_score
        opp.founder_confidence = snapshot.overall_confidence
        if snapshot.overall_confidence < 0.3:
            opp.next_founder_action = "Run structured cold-start assessment."
        else:
            opp.next_founder_action = "Run customer reference and team-scaling review."
        logger.info(
            "endpoint.screen_opportunity.end opportunity_id=%s founder_id=%s score=%s confidence=%s",
            opportunity_id,
            opp.founder_id,
            opp.founder_score,
            opp.founder_confidence,
        )
        return opp
    if opportunity_id not in OPPORTUNITIES:
        # Build demo opportunity for the first founder if available.
        founder_id = next(iter(FOUNDERS)) if FOUNDERS else None
        if not founder_id:
            raise HTTPException(status_code=404, detail="No founder available")
        snapshot = FOUNDERS[founder_id].latest_score_snapshot
        if not snapshot:
            snapshot = calculate_founder_score(founder_id, EVIDENCE.get(founder_id, []))
            FOUNDERS[founder_id].latest_score_snapshot = snapshot
        opp = OpportunityScreen(
            opportunity_id=opportunity_id,
            founder_id=founder_id,
            founder_score=snapshot.founder_score,
            founder_confidence=snapshot.overall_confidence,
            founder_market_fit=FounderMarketFit(score=72.0, confidence=0.42, coverage=0.35),
            team_completeness=TeamCompleteness(score=48.0, confidence=0.30, coverage=0.25),
            market_posture="neutral",
            market_confidence=0.35,
            idea_vs_market_posture="weak, pivotable",
            idea_vs_market_confidence=0.40,
            next_founder_action="Run customer reference and team-scaling review.",
        )
        OPPORTUNITIES[opportunity_id] = opp
    logger.info(
        "endpoint.screen_opportunity.end opportunity_id=%s founder_id=%s score=%s confidence=%s",
        opportunity_id,
        OPPORTUNITIES[opportunity_id].founder_id,
        OPPORTUNITIES[opportunity_id].founder_score,
        OPPORTUNITIES[opportunity_id].founder_confidence,
    )
    return OPPORTUNITIES[opportunity_id]


@app.get("/v1/opportunities/{opportunity_id}/diligence", response_model=List[Claim])
def get_diligence(opportunity_id: str):
    logger.info("endpoint.get_diligence.start opportunity_id=%s", opportunity_id)
    if opportunity_id not in CLAIMS:
        CLAIMS[opportunity_id] = [
            Claim(
                id=f"clm_{uuid.uuid4().hex[:8]}",
                opportunity_id=opportunity_id,
                claim="₹20 lakh ARR",
                source="Pitch deck slide 8",
                trust_status=TrustStatus.FOUNDER_REPORTED,
                confidence=0.35,
                contradiction="Bank statement not provided",
                owner="Diligence reviewer",
                next_action="Request bank statement or customer reference",
            ),
            Claim(
                id=f"clm_{uuid.uuid4().hex[:8]}",
                opportunity_id=opportunity_id,
                claim="15 active customers",
                source="Application form",
                trust_status=TrustStatus.SUPPORTED,
                confidence=0.65,
            next_action="Verify with two customer references",
        ),
    ]
    logger.info(
        "endpoint.get_diligence.end opportunity_id=%s claim_count=%s",
        opportunity_id,
        len(CLAIMS[opportunity_id]),
    )
    return CLAIMS[opportunity_id]


@app.post("/v1/seed")
def seed_demo():
    """Seed the hackathon demonstrator."""
    logger.info("endpoint.seed_demo.start")
    # Clear
    FOUNDERS.clear()
    EVIDENCE.clear()
    THESES.clear()
    OPPORTUNITIES.clear()
    CLAIMS.clear()

    # Create thesis
    thesis = create_thesis(
        CreateThesisRequest(
            name="Early-stage B2B SaaS",
            sectors=["B2B SaaS", "AI Infrastructure"],
            stages=["pre-seed", "seed"],
            geographies=["India", "Europe"],
            check_size_min=250_000,
            check_size_max=1_500_000,
            risk_appetite="moderate",
        )
    )

    # Create cold-start founder
    founder = create_founder(
        CreateFounderRequest(
            name="Maya Shah",
            email="maya@contextloop.example",
            current_company="ContextLoop",
            role="Founder",
            location="Bangalore",
        )
    )

    # No evidence => score near neutral with low confidence and clear unknowns.
    snapshot = calculate_founder_score(founder.id, [])
    FOUNDERS[founder.id].latest_score_snapshot = snapshot

    # Create opportunity
    opp_id = f"opp_{uuid.uuid4().hex[:8]}"
    OPPORTUNITIES[opp_id] = OpportunityScreen(
        opportunity_id=opp_id,
        founder_id=founder.id,
        founder_score=snapshot.founder_score,
        founder_confidence=snapshot.overall_confidence,
        founder_market_fit=FounderMarketFit(score=None, confidence=0.0, coverage=0.0),
        team_completeness=TeamCompleteness(score=None, confidence=0.0, coverage=0.0),
        market_posture="neutral",
        market_confidence=0.0,
        idea_vs_market_posture="neutral",
        idea_vs_market_confidence=0.0,
        next_founder_action="Run structured cold-start assessment.",
    )

    logger.info(
        "endpoint.seed_demo.end thesis_id=%s founder_id=%s opportunity_id=%s",
        thesis.id,
        founder.id,
        opp_id,
    )
    return {
        "thesis_id": thesis.id,
        "founder_id": founder.id,
        "opportunity_id": opp_id,
        "message": "Demo seeded. Founder score is near neutral with low confidence and clear unknowns.",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
