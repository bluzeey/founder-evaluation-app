import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
)
from scoring import calculate_founder_score
from research import UmansClient, create_founder_from_research, evidence_from_llm

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
    return {"status": "ok"}


@app.post("/v1/founders", response_model=Founder)
def create_founder(req: CreateFounderRequest):
    founder_id = f"fnd_{uuid.uuid4().hex[:8]}"
    founder = Founder(
        id=founder_id,
        name=req.name,
        email=req.email,
        current_company=req.current_company,
        role=req.role,
        location=req.location,
    )
    FOUNDERS[founder_id] = founder
    EVIDENCE[founder_id] = []
    return founder


@app.post("/v1/founders/research", response_model=Founder)
def research_founder(req: ResearchFounderRequest):
    """Research a founder with Umans AI web search and create a scored profile."""
    try:
        client = UmansClient()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        result = client.research(req.query, req.channels)
    except Exception as exc:
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

    return founder


@app.get("/v1/founders/{founder_id}", response_model=Founder)
def get_founder(founder_id: str):
    if founder_id not in FOUNDERS:
        raise HTTPException(status_code=404, detail="Founder not found")
    return FOUNDERS[founder_id]


@app.post("/v1/founders/{founder_id}/evidence", response_model=ScoreSnapshot)
def add_evidence(founder_id: str, req: AddEvidenceRequest):
    if founder_id not in FOUNDERS:
        raise HTTPException(status_code=404, detail="Founder not found")

    previous = FOUNDERS[founder_id].latest_score_snapshot
    existing = EVIDENCE.get(founder_id, [])
    for item in req.items:
        existing.append(item)
    EVIDENCE[founder_id] = existing

    snapshot = calculate_founder_score(founder_id, existing, previous)
    FOUNDERS[founder_id].latest_score_snapshot = snapshot
    return snapshot


@app.get("/v1/founders/{founder_id}/score", response_model=ScoreSnapshot)
def get_score(founder_id: str):
    if founder_id not in FOUNDERS:
        raise HTTPException(status_code=404, detail="Founder not found")
    snapshot = FOUNDERS[founder_id].latest_score_snapshot
    if not snapshot:
        snapshot = calculate_founder_score(founder_id, EVIDENCE.get(founder_id, []))
        FOUNDERS[founder_id].latest_score_snapshot = snapshot
    return snapshot


@app.get("/v1/founders/{founder_id}/history", response_model=List[ScoreSnapshot])
def get_history(founder_id: str):
    if founder_id not in FOUNDERS:
        raise HTTPException(status_code=404, detail="Founder not found")
    snapshot = FOUNDERS[founder_id].latest_score_snapshot
    return [snapshot] if snapshot else []


@app.post("/v1/theses", response_model=Thesis)
def create_thesis(req: CreateThesisRequest):
    thesis_id = f"ths_{uuid.uuid4().hex[:8]}"
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
    return thesis


@app.get("/v1/theses", response_model=List[Thesis])
def list_theses():
    return list(THESES.values())


@app.get("/v1/founders", response_model=List[Founder])
def list_founders():
    return list(FOUNDERS.values())


@app.post("/v1/assessments/plan")
def plan_assessment(founder_id: str):
    if founder_id not in FOUNDERS:
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

    return {
        "founder_id": founder_id,
        "recommended_modules": selected,
        "reason": "Cold-start or low-confidence dimensions require structured evidence.",
    }


@app.post("/v1/assessments/simulate", response_model=ScoreSnapshot)
def simulate_assessment(req: SimulateAssessmentRequest):
    if req.founder_id not in FOUNDERS:
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
    return snapshot


@app.post("/v1/opportunities/{opportunity_id}/screen", response_model=OpportunityScreen)
def screen_opportunity(opportunity_id: str):
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
    return OPPORTUNITIES[opportunity_id]


@app.get("/v1/opportunities/{opportunity_id}/diligence", response_model=List[Claim])
def get_diligence(opportunity_id: str):
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
    return CLAIMS[opportunity_id]


@app.post("/v1/seed")
def seed_demo():
    """Seed the hackathon demonstrator."""
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
