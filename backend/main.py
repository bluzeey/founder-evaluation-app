import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from logger_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

from database import get_db
import crud
import seed_data
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
    SourcingSchedule,
    SourcingJob,
    SourceConfig,
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
    run_sourcing_job,
)
from tasks.document_extraction import extract_document

app = FastAPI(title="FounderOS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class CreateSourcingScheduleRequest(BaseModel):
    thesis_id: str
    enabled: bool = True
    interval_seconds: int = 300
    max_leads_per_run: int = 10
    sources: List[SourceConfig] = []


class UpdateSourcingScheduleRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = None
    max_leads_per_run: Optional[int] = None
    sources: Optional[List[SourceConfig]] = None


@app.get("/health")
def health():
    logger.info("endpoint.health.ok")
    return {"status": "ok"}


@app.post("/v1/founders", response_model=Founder)
def create_founder(req: CreateFounderRequest, db: Session = Depends(get_db)):
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
    crud.create_founder(db, founder)

    # Auto-trigger social background research via Celery.
    background_id = f"soc_{uuid.uuid4().hex[:8]}"
    founder.social_background_id = background_id
    crud.update_founder(db, founder_id, {"social_background_id": background_id})
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
    return crud.founder_to_pydantic(db, crud.get_founder(db, founder_id))


def _apply_social_background(db: Session, founder_id: str) -> Optional[SocialMediaBackground]:
    """Reconcile a completed social background result from the DB into the founder record."""
    background = load_social_background(founder_id)
    if not background:
        return None

    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        return background

    crud.update_founder(db, founder_id, {"social_background_id": background.id})

    if background.status == "completed" and background.evidence_items:
        existing_items = crud.list_evidence_for_founder(db, founder_id)
        existing_ids = {item.id for item in existing_items}
        new_items = [
            item for item in background.evidence_items if item.id not in existing_ids
        ]
        if new_items:
            crud.add_evidence_items(db, founder_id, new_items)
            all_items = crud.list_evidence_for_founder(db, founder_id)
            db_founder = crud.get_founder(db, founder_id)
            previous = (
                crud.score_snapshot_to_pydantic(snapshot)
                if db_founder.latest_score_snapshot_id
                and (snapshot := crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id))
                else None
            )
            snapshot = calculate_founder_score(founder_id, all_items, previous)
            db_snapshot = crud.create_score_snapshot(db, snapshot)
            crud.update_founder(
                db, founder_id, {"latest_score_snapshot_id": db_snapshot.id}
            )

    return background


@app.get("/v1/founders/pool", response_model=List[FounderPoolItem])
def list_founder_pool(
    status: Optional[str] = None,
    job_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List AI-sourced founder pool recommendations."""
    db_items = crud.list_pool_items(db, status=status, job_id=job_id)
    logger.info("endpoint.list_founder_pool status=%s job_id=%s total=%s", status, job_id, len(db_items))
    if status:
        try:
            target = PoolItemStatus(status)
        except ValueError:
            logger.warning("endpoint.list_founder_pool.invalid_status status=%s", status)
            raise HTTPException(status_code=400, detail="Invalid status")
    return [crud.pool_item_to_pydantic(item) for item in db_items]


@app.post("/v1/founders/pool/refresh")
def refresh_founder_pool_endpoint(thesis_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Manually trigger the AI sourcing agent to discover new founders."""
    logger.info("endpoint.refresh_founder_pool.start thesis_id=%s", thesis_id)
    if thesis_id:
        db_thesis = crud.get_thesis(db, thesis_id)
        if not db_thesis:
            logger.warning("endpoint.refresh_founder_pool.thesis_not_found thesis_id=%s", thesis_id)
            raise HTTPException(status_code=404, detail="Thesis not found")
        thesis = crud.thesis_to_pydantic(db_thesis)
    else:
        thesis = None

    sources = None
    if thesis_id:
        db_schedule = crud.get_sourcing_schedule_by_thesis(db, thesis_id)
        if db_schedule:
            sources = [s.model_dump(mode="json") for s in crud.sourcing_schedule_to_pydantic(db_schedule).sources]

    task = refresh_pool_task.delay(
        sectors=thesis.sectors if thesis else None,
        stages=thesis.stages if thesis else None,
        geographies=thesis.geographies if thesis else None,
        risk_appetite=thesis.risk_appetite if thesis else "moderate",
        sources=sources,
        thesis_id=thesis_id,
    )
    logger.info(
        "endpoint.refresh_founder_pool.queued thesis_id=%s task_id=%s",
        thesis_id,
        task.id,
    )
    return {"task_id": task.id, "status": "queued"}


@app.post("/v1/founders/pool/{item_id}/approve", response_model=Founder)
def approve_pool_item(item_id: str, db: Session = Depends(get_db)):
    """Approve a pool recommendation and create a Founder record."""
    logger.info("endpoint.approve_pool_item.start item_id=%s", item_id)
    db_item = crud.get_pool_item(db, item_id)
    if not db_item:
        logger.warning("endpoint.approve_pool_item.not_found item_id=%s", item_id)
        raise HTTPException(status_code=404, detail="Pool item not found")
    item = crud.pool_item_to_pydantic(db_item)
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
    crud.create_founder(db, founder)

    # Auto-trigger social background research.
    background_id = f"soc_{uuid.uuid4().hex[:8]}"
    crud.update_founder(db, founder_id, {"social_background_id": background_id})
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

    crud.update_pool_item_status(db, item_id, PoolItemStatus.APPROVED.value)
    logger.info(
        "endpoint.approve_pool_item.end item_id=%s founder_id=%s background_id=%s",
        item_id,
        founder_id,
        background_id,
    )
    return crud.founder_to_pydantic(db, crud.get_founder(db, founder_id))


@app.post("/v1/founders/pool/{item_id}/dismiss")
def dismiss_pool_item(item_id: str, db: Session = Depends(get_db)):
    """Dismiss a pool recommendation."""
    logger.info("endpoint.dismiss_pool_item.start item_id=%s", item_id)
    db_item = crud.get_pool_item(db, item_id)
    if not db_item:
        logger.warning("endpoint.dismiss_pool_item.not_found item_id=%s", item_id)
        raise HTTPException(status_code=404, detail="Pool item not found")
    crud.update_pool_item_status(db, item_id, PoolItemStatus.DISMISSED.value)
    logger.info("endpoint.dismiss_pool_item.end item_id=%s", item_id)
    return {"id": item_id, "status": PoolItemStatus.DISMISSED.value}


@app.post("/v1/founders/research", response_model=Founder)
def research_founder(req: ResearchFounderRequest, db: Session = Depends(get_db)):
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
    crud.create_founder(db, founder)

    evidence_items = [evidence_from_llm(founder.id, item) for item in evidence_data]
    if req.auto_score and evidence_items:
        crud.add_evidence_items(db, founder.id, evidence_items)
        snapshot = calculate_founder_score(founder.id, evidence_items)
        db_snapshot = crud.create_score_snapshot(db, snapshot)
        crud.update_founder(db, founder.id, {"latest_score_snapshot_id": db_snapshot.id})

    logger.info(
        "endpoint.research_founder.end founder_id=%s name=%s evidence_count=%s scored=%s",
        founder.id,
        founder.name,
        len(evidence_items),
        req.auto_score and len(evidence_items) > 0,
    )
    return crud.founder_to_pydantic(db, crud.get_founder(db, founder.id))


@app.get("/v1/founders/{founder_id}", response_model=Founder)
def get_founder(founder_id: str, db: Session = Depends(get_db)):
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.get_founder.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    _apply_social_background(db, founder_id)
    logger.info("endpoint.get_founder.ok founder_id=%s", founder_id)
    return crud.founder_to_pydantic(db, db_founder)


@app.post("/v1/founders/{founder_id}/research-social")
def research_social(founder_id: str, db: Session = Depends(get_db)):
    """Manually re-run social background research for a founder."""
    logger.info("endpoint.research_social.start founder_id=%s", founder_id)
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.research_social.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")

    founder = crud.founder_to_pydantic(db, db_founder)
    background_id = f"soc_{uuid.uuid4().hex[:8]}"
    crud.update_founder(db, founder_id, {"social_background_id": background_id})
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
def get_social_background(founder_id: str, db: Session = Depends(get_db)):
    """Get the latest social background research result for a founder."""
    logger.info("endpoint.get_social_background.start founder_id=%s", founder_id)
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.get_social_background.founder_not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    background = _apply_social_background(db, founder_id)
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
def add_evidence(founder_id: str, req: AddEvidenceRequest, db: Session = Depends(get_db)):
    logger.info(
        "endpoint.add_evidence.start founder_id=%s item_count=%s",
        founder_id,
        len(req.items),
    )
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.add_evidence.founder_not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")

    previous = (
        crud.score_snapshot_to_pydantic(snapshot)
        if db_founder.latest_score_snapshot_id
        and (snapshot := crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id))
        else None
    )
    crud.add_evidence_items(db, founder_id, req.items)
    all_items = crud.list_evidence_for_founder(db, founder_id)
    snapshot = calculate_founder_score(founder_id, all_items, previous)
    db_snapshot = crud.create_score_snapshot(db, snapshot)
    crud.update_founder(db, founder_id, {"latest_score_snapshot_id": db_snapshot.id})

    logger.info(
        "endpoint.add_evidence.end founder_id=%s founder_score=%s confidence=%s",
        founder_id,
        snapshot.founder_score,
        snapshot.overall_confidence,
    )
    return crud.score_snapshot_to_pydantic(db_snapshot)


@app.get("/v1/founders/{founder_id}/score", response_model=ScoreSnapshot)
def get_score(founder_id: str, db: Session = Depends(get_db)):
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.get_score.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    if db_founder.latest_score_snapshot_id:
        db_snapshot = crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id)
        if db_snapshot:
            return crud.score_snapshot_to_pydantic(db_snapshot)
    all_items = crud.list_evidence_for_founder(db, founder_id)
    snapshot = calculate_founder_score(founder_id, all_items)
    db_snapshot = crud.create_score_snapshot(db, snapshot)
    crud.update_founder(db, founder_id, {"latest_score_snapshot_id": db_snapshot.id})
    logger.info(
        "endpoint.get_score.ok founder_id=%s founder_score=%s confidence=%s",
        founder_id,
        snapshot.founder_score,
        snapshot.overall_confidence,
    )
    return crud.score_snapshot_to_pydantic(db_snapshot)


@app.get("/v1/founders/{founder_id}/history", response_model=List[ScoreSnapshot])
def get_history(founder_id: str, db: Session = Depends(get_db)):
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.get_history.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")
    snapshots = crud.list_score_snapshots_for_founder(db, founder_id)
    logger.info(
        "endpoint.get_history.ok founder_id=%s snapshot_count=%s",
        founder_id,
        len(snapshots),
    )
    return snapshots


@app.post("/v1/theses", response_model=Thesis)
def create_thesis(req: CreateThesisRequest, db: Session = Depends(get_db)):
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
    db_thesis = crud.create_thesis(db, thesis)
    logger.info("endpoint.create_thesis.end thesis_id=%s", thesis_id)
    return crud.thesis_to_pydantic(db_thesis)


@app.get("/v1/theses", response_model=List[Thesis])
def list_theses(db: Session = Depends(get_db)):
    db_theses = crud.list_theses(db)
    logger.info("endpoint.list_theses count=%s", len(db_theses))
    return [crud.thesis_to_pydantic(t) for t in db_theses]


@app.get("/v1/founders", response_model=List[Founder])
def list_founders(db: Session = Depends(get_db)):
    db_founders = crud.list_founders(db)
    logger.info("endpoint.list_founders count=%s", len(db_founders))
    return [crud.founder_to_pydantic(db, f) for f in db_founders]


@app.post("/v1/assessments/plan")
def plan_assessment(founder_id: str, db: Session = Depends(get_db)):
    logger.info("endpoint.plan_assessment.start founder_id=%s", founder_id)
    db_founder = crud.get_founder(db, founder_id)
    if not db_founder:
        logger.warning("endpoint.plan_assessment.not_found founder_id=%s", founder_id)
        raise HTTPException(status_code=404, detail="Founder not found")

    db_snapshot = (
        crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id)
        if db_founder.latest_score_snapshot_id
        else None
    )
    if db_snapshot:
        snapshot = crud.score_snapshot_to_pydantic(db_snapshot)
    else:
        all_items = crud.list_evidence_for_founder(db, founder_id)
        snapshot = calculate_founder_score(founder_id, all_items)
        db_snapshot = crud.create_score_snapshot(db, snapshot)
        crud.update_founder(db, founder_id, {"latest_score_snapshot_id": db_snapshot.id})

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
def simulate_assessment(req: SimulateAssessmentRequest, db: Session = Depends(get_db)):
    logger.info(
        "endpoint.simulate_assessment.start founder_id=%s modules=%s",
        req.founder_id,
        [m.value for m in req.modules],
    )
    db_founder = crud.get_founder(db, req.founder_id)
    if not db_founder:
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

    previous = (
        crud.score_snapshot_to_pydantic(snapshot)
        if db_founder.latest_score_snapshot_id
        and (snapshot := crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id))
        else None
    )
    crud.add_evidence_items(db, req.founder_id, new_evidence)
    all_items = crud.list_evidence_for_founder(db, req.founder_id)
    snapshot = calculate_founder_score(req.founder_id, all_items, previous)
    db_snapshot = crud.create_score_snapshot(db, snapshot)
    crud.update_founder(db, req.founder_id, {"latest_score_snapshot_id": db_snapshot.id})
    logger.info(
        "endpoint.simulate_assessment.end founder_id=%s founder_score=%s confidence=%s",
        req.founder_id,
        snapshot.founder_score,
        snapshot.overall_confidence,
    )
    return crud.score_snapshot_to_pydantic(db_snapshot)


@app.post("/v1/opportunities/{opportunity_id}/screen", response_model=OpportunityScreen)
def screen_opportunity(
    opportunity_id: str,
    founder_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    logger.info("endpoint.screen_opportunity.start opportunity_id=%s founder_id=%s", opportunity_id, founder_id)
    db_opp = crud.get_opportunity(db, opportunity_id)
    if db_opp:
        opp = crud.opportunity_to_pydantic(db_opp)
        db_founder = crud.get_founder(db, opp.founder_id)
        if db_founder and db_founder.latest_score_snapshot_id:
            db_snapshot = crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id)
            if db_snapshot:
                snapshot = crud.score_snapshot_to_pydantic(db_snapshot)
                opp.founder_score = snapshot.founder_score
                opp.founder_confidence = snapshot.overall_confidence
        if opp.founder_confidence < 0.3:
            opp.next_founder_action = "Run structured cold-start assessment."
        else:
            opp.next_founder_action = "Run customer reference and team-scaling review."
        crud.create_or_update_opportunity(db, opp)
        logger.info(
            "endpoint.screen_opportunity.end opportunity_id=%s founder_id=%s score=%s confidence=%s",
            opportunity_id,
            opp.founder_id,
            opp.founder_score,
            opp.founder_confidence,
        )
        return opp

    # Build a demo opportunity for the requested founder or the first available founder.
    if founder_id:
        db_founder = crud.get_founder(db, founder_id)
        if not db_founder:
            raise HTTPException(status_code=404, detail="Founder not found")
    else:
        db_founders = crud.list_founders(db)
        if not db_founders:
            raise HTTPException(status_code=404, detail="No founder available")
        db_founder = db_founders[0]
    founder_id = db_founder.id
    all_items = crud.list_evidence_for_founder(db, founder_id)
    if db_founder.latest_score_snapshot_id:
        db_snapshot = crud.get_score_snapshot(db, db_founder.latest_score_snapshot_id)
        snapshot = crud.score_snapshot_to_pydantic(db_snapshot) if db_snapshot else None
    else:
        snapshot = calculate_founder_score(founder_id, all_items)
        db_snapshot = crud.create_score_snapshot(db, snapshot)
        crud.update_founder(db, founder_id, {"latest_score_snapshot_id": db_snapshot.id})

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
    crud.create_or_update_opportunity(db, opp)
    logger.info(
        "endpoint.screen_opportunity.end opportunity_id=%s founder_id=%s score=%s confidence=%s",
        opportunity_id,
        opp.founder_id,
        opp.founder_score,
        opp.founder_confidence,
    )
    return opp


@app.get("/v1/opportunities", response_model=List[OpportunityScreen])
def list_opportunities(db: Session = Depends(get_db)):
    db_opps = crud.list_opportunities(db)
    logger.info("endpoint.list_opportunities count=%s", len(db_opps))
    return [crud.opportunity_to_pydantic(o) for o in db_opps]


@app.get("/v1/opportunities/{opportunity_id}", response_model=OpportunityScreen)
def get_opportunity_screen(opportunity_id: str, db: Session = Depends(get_db)):
    logger.info("endpoint.get_opportunity_screen.start opportunity_id=%s", opportunity_id)
    db_opp = crud.get_opportunity(db, opportunity_id)
    if not db_opp:
        logger.warning("endpoint.get_opportunity_screen.not_found opportunity_id=%s", opportunity_id)
        raise HTTPException(status_code=404, detail="Opportunity not found")
    logger.info("endpoint.get_opportunity_screen.end opportunity_id=%s", opportunity_id)
    return crud.opportunity_to_pydantic(db_opp)


@app.get("/v1/opportunities/{opportunity_id}/diligence", response_model=List[Claim])
def get_diligence(opportunity_id: str, db: Session = Depends(get_db)):
    logger.info("endpoint.get_diligence.start opportunity_id=%s", opportunity_id)
    claims = crud.list_claims_for_opportunity(db, opportunity_id)
    if not claims:
        claims = [
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
        crud.create_claims(db, claims)
    logger.info(
        "endpoint.get_diligence.end opportunity_id=%s claim_count=%s",
        opportunity_id,
        len(claims),
    )
    return claims


@app.post("/v1/seed")
def seed_demo(db: Session = Depends(get_db)):
    """Seed the hackathon demonstrator."""
    logger.info("endpoint.seed_demo.start")

    # Clear tables in a safe order.
    from sqlalchemy import text
    db.execute(text("TRUNCATE sourcing_jobs, sourcing_schedules, claims, opportunities, score_snapshots, evidence_items, social_media_backgrounds, founder_pool_items, theses, founders CASCADE"))
    db.commit()

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
        ),
        db,
    )

    # Create a default recurring sourcing schedule for the thesis so the agent keeps collecting leads.
    # Runs every 5 minutes with LinkedIn and Twitter keyword searches based on the thesis.
    schedule_id = f"sch_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    default_sources = [
        SourceConfig(platform="linkedin", keywords=f"{', '.join(thesis.sectors)} founders {', '.join(thesis.geographies)}"),
        SourceConfig(platform="twitter", keywords=f"{', '.join(thesis.sectors)} startup founder {', '.join(thesis.geographies)}"),
    ]
    default_schedule = SourcingSchedule(
        id=schedule_id,
        thesis_id=thesis.id,
        enabled=True,
        interval_seconds=300,
        max_leads_per_run=10,
        sources=default_sources,
        next_run_at=now,
        created_at=now,
        updated_at=now,
    )
    crud.create_sourcing_schedule(db, default_schedule)

    # Create cold-start founder
    founder = create_founder(
        CreateFounderRequest(
            name="Maya Shah",
            email="maya@contextloop.example",
            current_company="ContextLoop",
            role="Founder",
            location="Bangalore",
        ),
        db,
    )

    # No evidence => score near neutral with low confidence and clear unknowns.
    db_founder = crud.get_founder(db, founder.id)
    snapshot = calculate_founder_score(founder.id, [])
    db_snapshot = crud.create_score_snapshot(db, snapshot)
    crud.update_founder(db, founder.id, {"latest_score_snapshot_id": db_snapshot.id})

    # Create opportunity
    opp_id = f"opp_{uuid.uuid4().hex[:8]}"
    opp = OpportunityScreen(
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
    crud.create_or_update_opportunity(db, opp)

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


@app.post("/v1/seed/all")
def seed_all(db: Session = Depends(get_db)):
    """Idempotently seed AI theses, schedules, sample founders, opportunities, and pool items.

    Safe to call multiple times in production: it only creates records that do not already exist.
    """
    logger.info("endpoint.seed_all.start")
    now = datetime.now(timezone.utc)

    created_theses = []
    created_schedules = []
    created_founders = []
    created_opportunities = []
    created_pool_items = []

    # 1. AI theses + 5-minute schedules.
    for thesis_data in seed_data.AI_THESES:
        db_thesis = crud.get_thesis(db, thesis_data["id"])
        if not db_thesis:
            thesis = Thesis(
                id=thesis_data["id"],
                name=thesis_data["name"],
                sectors=thesis_data["sectors"],
                stages=thesis_data["stages"],
                geographies=thesis_data["geographies"],
                check_size_min=thesis_data["check_size_min"],
                check_size_max=thesis_data["check_size_max"],
                risk_appetite=thesis_data["risk_appetite"],
                min_evidence_requirements=thesis_data.get("min_evidence_requirements", {}),
            )
            db_thesis = crud.create_thesis(db, thesis)
            created_theses.append(thesis.id)
            logger.info("endpoint.seed_all.created_thesis thesis_id=%s", thesis.id)
        else:
            logger.info("endpoint.seed_all.thesis_exists thesis_id=%s", thesis_data["id"])

        thesis_id = thesis_data["id"]
        existing_schedule = crud.get_sourcing_schedule_by_thesis(db, thesis_id)
        if not existing_schedule:
            thesis_pydantic = crud.thesis_to_pydantic(db_thesis)
            sources = seed_data.default_sources_for_thesis(thesis_pydantic)
            schedule_id = f"sch_{uuid.uuid4().hex[:8]}"
            schedule = SourcingSchedule(
                id=schedule_id,
                thesis_id=thesis_id,
                enabled=True,
                interval_seconds=300,
                max_leads_per_run=10,
                sources=sources,
                next_run_at=now,
                created_at=now,
                updated_at=now,
            )
            crud.create_sourcing_schedule(db, schedule)
            created_schedules.append(schedule_id)
            logger.info("endpoint.seed_all.created_schedule schedule_id=%s thesis_id=%s", schedule_id, thesis_id)

    # 2. Sample founders.
    for founder_data in seed_data.SAMPLE_FOUNDERS:
        db_founder = crud.get_founder(db, founder_data["id"])
        if not db_founder:
            founder = Founder(
                id=founder_data["id"],
                name=founder_data["name"],
                email=founder_data["email"],
                current_company=founder_data["current_company"],
                role=founder_data["role"],
                location=founder_data["location"],
                linkedin_url=founder_data.get("linkedin_url"),
                github_url=founder_data.get("github_url"),
            )
            crud.create_founder(db, founder)
            created_founders.append(founder.id)
            logger.info("endpoint.seed_all.created_founder founder_id=%s", founder.id)

            # Trigger social background research automatically (matches create_founder behavior).
            background_id = f"soc_{uuid.uuid4().hex[:8]}"
            crud.update_founder(db, founder.id, {"social_background_id": background_id})
            from tasks.social_research import store_social_background, research_social_background
            pending = SocialMediaBackground(
                id=background_id,
                founder_id=founder.id,
                status="pending",
                linkedin_url=founder.linkedin_url,
                github_url=founder.github_url,
            )
            store_social_background(pending)
            research_social_background.delay(
                founder_id=founder.id,
                name=founder.name,
                email=founder.email,
                linkedin_url=founder.linkedin_url,
                github_url=founder.github_url,
                auto_score=True,
            )
        else:
            logger.info("endpoint.seed_all.founder_exists founder_id=%s", founder_data["id"])

    # 3. Sample opportunities.
    for opp_data in seed_data.SAMPLE_OPPORTUNITIES:
        db_opp = crud.get_opportunity(db, opp_data["opportunity_id"])
        if not db_opp:
            opp = OpportunityScreen(
                opportunity_id=opp_data["opportunity_id"],
                founder_id=opp_data["founder_id"],
                founder_score=opp_data["founder_score"],
                founder_confidence=opp_data["founder_confidence"],
                founder_market_fit=FounderMarketFit(score=None, confidence=0.0, coverage=0.0),
                team_completeness=TeamCompleteness(score=None, confidence=0.0, coverage=0.0),
                market_posture=opp_data["market_posture"],
                market_confidence=opp_data["market_confidence"],
                idea_vs_market_posture=opp_data["idea_vs_market_posture"],
                idea_vs_market_confidence=opp_data["idea_vs_market_confidence"],
                next_founder_action=opp_data["next_founder_action"],
            )
            crud.create_or_update_opportunity(db, opp)
            created_opportunities.append(opp_data["opportunity_id"])
            logger.info("endpoint.seed_all.created_opportunity opportunity_id=%s", opp_data["opportunity_id"])
        else:
            logger.info("endpoint.seed_all.opportunity_exists opportunity_id=%s", opp_data["opportunity_id"])

    # 4. Sample pool items.
    for item_data in seed_data.SAMPLE_POOL_ITEMS:
        db_item = crud.get_pool_item(db, item_data["id"])
        if not db_item:
            item = FounderPoolItem(
                id=item_data["id"],
                name=item_data["name"],
                email=item_data["email"],
                current_company=item_data["current_company"],
                role=item_data["role"],
                location=item_data["location"],
                linkedin_url=item_data.get("linkedin_url"),
                github_url=item_data.get("github_url"),
                source_url=item_data.get("source_url"),
                source=item_data.get("source"),
                reason=item_data["reason"],
                status=PoolItemStatus.RECOMMENDED,
                created_at=now,
            )
            crud.create_pool_items(db, [item])
            created_pool_items.append(item_data["id"])
            logger.info("endpoint.seed_all.created_pool_item item_id=%s", item_data["id"])
        else:
            logger.info("endpoint.seed_all.pool_item_exists item_id=%s", item_data["id"])

    logger.info(
        "endpoint.seed_all.end theses=%s schedules=%s founders=%s opportunities=%s pool_items=%s",
        len(created_theses),
        len(created_schedules),
        len(created_founders),
        len(created_opportunities),
        len(created_pool_items),
    )
    return {
        "theses_created": created_theses,
        "schedules_created": created_schedules,
        "founders_created": created_founders,
        "opportunities_created": created_opportunities,
        "pool_items_created": created_pool_items,
        "message": "Seed applied. Existing records were skipped.",
    }


@app.post("/v1/opportunities/{opportunity_id}/deck")
def upload_deck(
    opportunity_id: str,
    file: UploadFile = File(...),
    founder_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Upload a deck (PDF/DOCX/TXT/MD), extract claims and evidence via AI, and discard the file.

    The file itself is not stored; only the structured extraction is persisted.
    """
    logger.info(
        "endpoint.upload_deck.start opportunity_id=%s founder_id=%s filename=%s content_type=%s",
        opportunity_id,
        founder_id,
        file.filename,
        file.content_type,
    )

    db_opp = crud.get_opportunity(db, opportunity_id)
    if not db_opp:
        logger.warning("endpoint.upload_deck.opportunity_not_found opportunity_id=%s", opportunity_id)
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if founder_id:
        db_founder = crud.get_founder(db, founder_id)
        if not db_founder:
            logger.warning("endpoint.upload_deck.founder_not_found founder_id=%s", founder_id)
            raise HTTPException(status_code=404, detail="Founder not found")

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    import base64

    task = extract_document.delay(
        base64.b64encode(file_bytes).decode("utf-8"),
        filename=file.filename or "document",
        opportunity_id=opportunity_id,
        founder_id=founder_id,
    )
    logger.info(
        "endpoint.upload_deck.queued opportunity_id=%s task_id=%s",
        opportunity_id,
        task.id,
    )
    return {
        "opportunity_id": opportunity_id,
        "founder_id": founder_id,
        "task_id": task.id,
        "status": "queued",
    }


@app.get("/v1/sourcing/schedules", response_model=List[SourcingSchedule])
def list_sourcing_schedules(db: Session = Depends(get_db)):
    db_schedules = crud.list_sourcing_schedules(db)
    logger.info("endpoint.list_sourcing_schedules count=%s", len(db_schedules))
    return [crud.sourcing_schedule_to_pydantic(s) for s in db_schedules]


@app.post("/v1/sourcing/schedules", response_model=SourcingSchedule)
def create_sourcing_schedule(
    req: CreateSourcingScheduleRequest, db: Session = Depends(get_db)
):
    db_thesis = crud.get_thesis(db, req.thesis_id)
    if not db_thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")

    existing = crud.get_sourcing_schedule_by_thesis(db, req.thesis_id)
    if existing:
        raise HTTPException(status_code=400, detail="Sourcing schedule already exists for this thesis")

    schedule_id = f"sch_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    schedule = SourcingSchedule(
        id=schedule_id,
        thesis_id=req.thesis_id,
        enabled=req.enabled,
        interval_seconds=req.interval_seconds,
        max_leads_per_run=req.max_leads_per_run,
        sources=req.sources,
        next_run_at=now,
        created_at=now,
        updated_at=now,
    )
    db_schedule = crud.create_sourcing_schedule(db, schedule)
    logger.info(
        "endpoint.create_sourcing_schedule schedule_id=%s thesis_id=%s interval=%s",
        schedule_id,
        req.thesis_id,
        req.interval_seconds,
    )
    return crud.sourcing_schedule_to_pydantic(db_schedule)


@app.get("/v1/sourcing/schedules/{schedule_id}", response_model=SourcingSchedule)
def get_sourcing_schedule(schedule_id: str, db: Session = Depends(get_db)):
    db_schedule = crud.get_sourcing_schedule(db, schedule_id)
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Sourcing schedule not found")
    return crud.sourcing_schedule_to_pydantic(db_schedule)


@app.put("/v1/sourcing/schedules/{schedule_id}", response_model=SourcingSchedule)
def update_sourcing_schedule(
    schedule_id: str, req: UpdateSourcingScheduleRequest, db: Session = Depends(get_db)
):
    db_schedule = crud.get_sourcing_schedule(db, schedule_id)
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Sourcing schedule not found")

    updates = req.model_dump(exclude_unset=True)
    if not updates:
        return crud.sourcing_schedule_to_pydantic(db_schedule)

    db_schedule = crud.update_sourcing_schedule(db, schedule_id, updates)
    logger.info("endpoint.update_sourcing_schedule schedule_id=%s updates=%s", schedule_id, updates)
    return crud.sourcing_schedule_to_pydantic(db_schedule)


@app.delete("/v1/sourcing/schedules/{schedule_id}")
def delete_sourcing_schedule(schedule_id: str, db: Session = Depends(get_db)):
    deleted = crud.delete_sourcing_schedule(db, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sourcing schedule not found")
    logger.info("endpoint.delete_sourcing_schedule schedule_id=%s", schedule_id)
    return {"id": schedule_id, "deleted": True}


@app.post("/v1/theses/{thesis_id}/source-now")
def source_now(thesis_id: str, db: Session = Depends(get_db)):
    """Manually trigger a sourcing job for a thesis."""
    db_thesis = crud.get_thesis(db, thesis_id)
    if not db_thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")

    job_id = run_sourcing_job(thesis_id)
    logger.info("endpoint.source_now thesis_id=%s job_id=%s", thesis_id, job_id)
    return {"thesis_id": thesis_id, "job_id": job_id, "status": "queued"}


@app.get("/v1/sourcing/jobs", response_model=List[SourcingJob])
def list_sourcing_jobs(
    thesis_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    db_jobs = crud.list_sourcing_jobs(db, thesis_id=thesis_id, status=status)
    logger.info("endpoint.list_sourcing_jobs count=%s", len(db_jobs))
    return [crud.sourcing_job_to_pydantic(j) for j in db_jobs]


def _last_dispatch_time() -> Optional[str]:
    import redis

    redis_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        return client.get("sourcing:last_dispatch_at")
    except Exception:
        return None


@app.get("/v1/sourcing/status")
def get_sourcing_status(db: Session = Depends(get_db)):
    """Return the current state of sourcing: schedules, active jobs, recent jobs, and beat health."""
    schedules = [
        crud.sourcing_schedule_to_pydantic(s)
        for s in crud.list_sourcing_schedules(db)
    ]
    active_jobs = [
        crud.sourcing_job_to_pydantic(j)
        for j in crud.list_sourcing_jobs(db, status="running")
    ]
    recent_jobs = [
        crud.sourcing_job_to_pydantic(j)
        for j in crud.list_sourcing_jobs(db, limit=10)
    ]
    last_dispatch = _last_dispatch_time()

    logger.info(
        "endpoint.get_sourcing_status schedules=%s active_jobs=%s recent_jobs=%s last_dispatch=%s",
        len(schedules),
        len(active_jobs),
        len(recent_jobs),
        last_dispatch,
    )
    return {
        "schedules": [s.model_dump(mode="json") for s in schedules],
        "active_jobs": [j.model_dump(mode="json") for j in active_jobs],
        "recent_jobs": [j.model_dump(mode="json") for j in recent_jobs],
        "last_dispatch_at": last_dispatch,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
