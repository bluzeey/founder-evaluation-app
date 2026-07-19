"""seed ai thesis and sample data

Revision ID: f6cea5e9817c
Revises: 45a509d755d8
Create Date: 2026-07-19 13:10:31.136625

"""
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'f6cea5e9817c'
down_revision: Union[str, Sequence[str], None] = '45a509d755d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NOW = datetime.now(timezone.utc)

AI_THESES = [
    {
        "id": "demo_ths_ai_infra",
        "name": "AI Infrastructure",
        "sectors": ["AI Infrastructure", "B2B SaaS"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["United States", "Europe"],
        "check_size_min": 250000,
        "check_size_max": 1500000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_ai_agents",
        "name": "AI Agents & Automation",
        "sectors": ["AI Agents", "Automation", "AI Software"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["Global"],
        "check_size_min": 100000,
        "check_size_max": 1000000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_ai_dev_tools",
        "name": "AI Developer Tools",
        "sectors": ["Developer Tools", "AI Software"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["United States", "India"],
        "check_size_min": 250000,
        "check_size_max": 1000000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_vertical_ai",
        "name": "Vertical AI SaaS",
        "sectors": ["Vertical SaaS", "AI Software"],
        "stages": ["seed"],
        "geographies": ["India", "Europe"],
        "check_size_min": 250000,
        "check_size_max": 1000000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_india_ai",
        "name": "India-first AI",
        "sectors": ["AI Infrastructure", "AI Software"],
        "stages": ["pre-seed"],
        "geographies": ["India"],
        "check_size_min": 100000,
        "check_size_max": 500000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
]


SAMPLE_FOUNDERS = [
    {
        "id": "demo_fnd_talent_a",
        "name": "Alex Rivera",
        "email": "alex.rivera.demo@founderos.example",
        "current_company": "ML Code Review",
        "role": "Solo builder / ML engineer",
        "location": "Berlin, Germany",
        "linkedin_url": "https://linkedin.example/in/alexrivera",
        "github_url": "https://github.com/arivera/ml-code-review",
        "ai_research_summary": None,
        "ai_research_sources": [],
        "social_background_id": None,
        "latest_score_snapshot_id": None,
    },
    {
        "id": "demo_fnd_founder_b",
        "name": "Sam Okonkwo",
        "email": "sam.okonkwo.demo@founderos.example",
        "current_company": "PromptBridge",
        "role": "Founder / CEO",
        "location": "San Francisco, United States",
        "linkedin_url": "https://linkedin.example/in/sokonkwo",
        "github_url": "https://github.com/sokonkwo",
        "ai_research_summary": None,
        "ai_research_sources": [],
        "social_background_id": None,
        "latest_score_snapshot_id": None,
    },
    {
        "id": "demo_fnd_founder_c",
        "name": "Priya Nair",
        "email": "priya.nair.demo@founderos.example",
        "current_company": "TractionAI",
        "role": "Founder / CEO",
        "location": "Austin, United States",
        "linkedin_url": "https://linkedin.example/in/priyanair",
        "github_url": "https://github.com/tractionai",
        "ai_research_summary": None,
        "ai_research_sources": [],
        "social_background_id": None,
        "latest_score_snapshot_id": None,
    },
]


SAMPLE_OPPORTUNITIES = [
    {
        "id": "demo_opp_cold_start",
        "founder_id": "demo_fnd_talent_a",
        "founder_score": 0.62,
        "founder_confidence": 0.55,
        "founder_market_fit": {},
        "team_completeness": {},
        "market_posture": "neutral",
        "market_confidence": 0.4,
        "idea_vs_market_posture": "weak, pivotable",
        "idea_vs_market_confidence": 0.45,
        "next_founder_action": "Run structured cold-start assessment.",
    },
    {
        "id": "demo_opp_founder_spike",
        "founder_id": "demo_fnd_founder_b",
        "founder_score": 0.78,
        "founder_confidence": 0.68,
        "founder_market_fit": {},
        "team_completeness": {},
        "market_posture": "neutral",
        "market_confidence": 0.45,
        "idea_vs_market_posture": "weak, pivotable",
        "idea_vs_market_confidence": 0.5,
        "next_founder_action": "Run customer reference and team-scaling review.",
    },
    {
        "id": "demo_opp_contradictory_traction",
        "founder_id": "demo_fnd_founder_c",
        "founder_score": 0.65,
        "founder_confidence": 0.5,
        "founder_market_fit": {},
        "team_completeness": {},
        "market_posture": "neutral",
        "market_confidence": 0.55,
        "idea_vs_market_posture": "plausible, unvalidated",
        "idea_vs_market_confidence": 0.55,
        "next_founder_action": "Resolve revenue/customer adoption contradiction with bank statement or customer references.",
    },
]


SAMPLE_POOL_ITEMS = [
    {
        "id": "demo_pool_001",
        "name": "Alex Rivera",
        "email": "alex.rivera.demo@founderos.example",
        "current_company": "ML Code Review",
        "role": "Solo builder / ML engineer",
        "location": "Berlin, Germany",
        "linkedin_url": "https://linkedin.example/in/alexrivera",
        "github_url": "https://github.com/arivera/ml-code-review",
        "source_url": "https://github.com/arivera/ml-code-review",
        "source": "linkedin",
        "reason": "Shipped a working RAG code-review prototype in 48 hours; strong execution signal.",
        "thesis_id": None,
        "job_id": None,
        "status": "recommended",
    },
    {
        "id": "demo_pool_002",
        "name": "Sam Okonkwo",
        "email": "sam.okonkwo.demo@founderos.example",
        "current_company": "PromptBridge",
        "role": "Founder / CEO",
        "location": "San Francisco, United States",
        "linkedin_url": "https://linkedin.example/in/sokonkwo",
        "github_url": "https://github.com/sokonkwo",
        "source_url": "https://github.com/sokonkwo",
        "source": "twitter",
        "reason": "Verified execution record in AI infrastructure; led two production launches.",
        "thesis_id": None,
        "job_id": None,
        "status": "recommended",
    },
    {
        "id": "demo_pool_003",
        "name": "Priya Nair",
        "email": "priya.nair.demo@founderos.example",
        "current_company": "TractionAI",
        "role": "Founder / CEO",
        "location": "Austin, United States",
        "linkedin_url": "https://linkedin.example/in/priyanair",
        "github_url": "https://github.com/tractionai",
        "source_url": "https://tractionai.example/launch",
        "source": "linkedin",
        "reason": "Technical founder building AI infrastructure observability; plausible wedge.",
        "thesis_id": None,
        "job_id": None,
        "status": "recommended",
    },
]


def _default_sources_for_thesis(thesis: dict) -> list:
    sectors = ", ".join(thesis["sectors"])
    geographies = ", ".join(thesis["geographies"])
    return [
        {"platform": "linkedin", "keywords": f"{sectors} founders {geographies}"},
        {"platform": "twitter", "keywords": f"{sectors} startup founder {geographies}"},
    ]


def _exists(bind, table_name: str, column: str, value: str) -> bool:
    table = sa.table(table_name, sa.column(column))
    return bool(bind.execute(sa.select(table.c[column]).where(table.c[column] == value)).scalar_one_or_none())


def upgrade() -> None:
    bind = op.get_bind()

    # Idempotency: skip the whole seed if the first thesis is already present.
    if _exists(bind, "theses", "id", AI_THESES[0]["id"]):
        return

    theses_table = sa.table(
        "theses",
        sa.column("id"),
        sa.column("name"),
        sa.column("sectors", JSONB),
        sa.column("stages", JSONB),
        sa.column("geographies", JSONB),
        sa.column("check_size_min"),
        sa.column("check_size_max"),
        sa.column("risk_appetite"),
        sa.column("min_evidence_requirements", JSONB),
        sa.column("created_at"),
    )
    op.bulk_insert(
        theses_table,
        [{**t, "created_at": NOW} for t in AI_THESES],
    )

    schedules_table = sa.table(
        "sourcing_schedules",
        sa.column("id"),
        sa.column("thesis_id"),
        sa.column("enabled"),
        sa.column("interval_seconds"),
        sa.column("max_leads_per_run"),
        sa.column("sources", JSONB),
        sa.column("last_run_at"),
        sa.column("next_run_at"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    DEFAULT_INTERVAL_SECONDS = 3600
    schedule_rows = []
    for idx, thesis in enumerate(AI_THESES):
        total = len(AI_THESES)
        stagger_seconds = (DEFAULT_INTERVAL_SECONDS // total) * idx
        schedule_rows.append(
            {
                "id": f"demo_sch_{idx + 1}",
                "thesis_id": thesis["id"],
                "enabled": True,
                "interval_seconds": DEFAULT_INTERVAL_SECONDS,
                "max_leads_per_run": 10,
                "sources": _default_sources_for_thesis(thesis),
                "last_run_at": None,
                "next_run_at": NOW + timedelta(seconds=stagger_seconds),
                "created_at": NOW,
                "updated_at": NOW,
            }
        )
    op.bulk_insert(schedules_table, schedule_rows)

    founders_table = sa.table(
        "founders",
        sa.column("id"),
        sa.column("name"),
        sa.column("email"),
        sa.column("current_company"),
        sa.column("role"),
        sa.column("location"),
        sa.column("linkedin_url"),
        sa.column("github_url"),
        sa.column("ai_research_summary"),
        sa.column("ai_research_sources", JSONB),
        sa.column("social_background_id"),
        sa.column("latest_score_snapshot_id"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    op.bulk_insert(
        founders_table,
        [{**f, "created_at": NOW, "updated_at": NOW} for f in SAMPLE_FOUNDERS],
    )

    opportunities_table = sa.table(
        "opportunities",
        sa.column("id"),
        sa.column("founder_id"),
        sa.column("founder_score"),
        sa.column("founder_confidence"),
        sa.column("founder_market_fit", JSONB),
        sa.column("team_completeness", JSONB),
        sa.column("market_posture"),
        sa.column("market_confidence"),
        sa.column("idea_vs_market_posture"),
        sa.column("idea_vs_market_confidence"),
        sa.column("next_founder_action"),
    )
    op.bulk_insert(opportunities_table, SAMPLE_OPPORTUNITIES)

    pool_items_table = sa.table(
        "founder_pool_items",
        sa.column("id"),
        sa.column("name"),
        sa.column("email"),
        sa.column("current_company"),
        sa.column("role"),
        sa.column("location"),
        sa.column("linkedin_url"),
        sa.column("github_url"),
        sa.column("source_url"),
        sa.column("source"),
        sa.column("reason"),
        sa.column("thesis_id"),
        sa.column("job_id"),
        sa.column("status"),
        sa.column("created_at"),
    )
    op.bulk_insert(
        pool_items_table,
        [{**p, "created_at": NOW} for p in SAMPLE_POOL_ITEMS],
    )


def downgrade() -> None:
    bind = op.get_bind()

    pool_ids = [p["id"] for p in SAMPLE_POOL_ITEMS]
    opp_ids = [o["id"] for o in SAMPLE_OPPORTUNITIES]
    founder_ids = [f["id"] for f in SAMPLE_FOUNDERS]
    thesis_ids = [t["id"] for t in AI_THESES]

    bind.execute(sa.delete(sa.table("founder_pool_items")).where(sa.column("id").in_(pool_ids)))
    bind.execute(sa.delete(sa.table("opportunities")).where(sa.column("id").in_(opp_ids)))
    bind.execute(sa.delete(sa.table("founders")).where(sa.column("id").in_(founder_ids)))
    bind.execute(sa.delete(sa.table("sourcing_schedules")).where(sa.column("thesis_id").in_(thesis_ids)))
    bind.execute(sa.delete(sa.table("theses")).where(sa.column("id").in_(thesis_ids)))
