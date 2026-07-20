"""Idempotent seed data for production onboarding.

Contains AI-focused theses, sample founders, opportunities, and pool items.
All IDs are prefixed with "demo_" to avoid collisions with live data.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import List, Dict, Any

from models import SourceConfig, Thesis

# Default cadence for seeded sourcing schedules. 1 hour is conservative for live
# web-search LLM calls and avoids rate-limit storms.
DEFAULT_SOURCING_INTERVAL_SECONDS = int(
    os.environ.get("DEFAULT_SOURCING_INTERVAL_SECONDS", "3600")
)
FOUNDER_IMPORT_DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "founderos_delivery_bundle_2026-07-20"
    / "founderos_founder_import_150.csv"
)

# ---------------------------------------------------------------------------
# AI-focused theses with default 5-minute sourcing schedules.
# ---------------------------------------------------------------------------

AI_THESES: List[Dict[str, Any]] = [
    {
        "id": "demo_ths_ai_infra",
        "name": "AI Infrastructure",
        "sectors": ["AI Infrastructure", "B2B SaaS"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["United States", "Europe"],
        "check_size_min": 250_000,
        "check_size_max": 1_500_000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_ai_agents",
        "name": "AI Agents & Automation",
        "sectors": ["AI Agents", "Automation", "AI Software"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["Global"],
        "check_size_min": 100_000,
        "check_size_max": 1_000_000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_ai_dev_tools",
        "name": "AI Developer Tools",
        "sectors": ["Developer Tools", "AI Software"],
        "stages": ["pre-seed", "seed"],
        "geographies": ["United States", "India"],
        "check_size_min": 250_000,
        "check_size_max": 1_000_000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_vertical_ai",
        "name": "Vertical AI SaaS",
        "sectors": ["Vertical SaaS", "AI Software"],
        "stages": ["seed"],
        "geographies": ["India", "Europe"],
        "check_size_min": 250_000,
        "check_size_max": 1_000_000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
    {
        "id": "demo_ths_india_ai",
        "name": "India-first AI",
        "sectors": ["AI Infrastructure", "AI Software"],
        "stages": ["pre-seed"],
        "geographies": ["India"],
        "check_size_min": 100_000,
        "check_size_max": 500_000,
        "risk_appetite": "moderate",
        "min_evidence_requirements": {},
    },
]


def staggered_next_run_at(
    now: datetime,
    index: int,
    total: int,
    interval_seconds: int = DEFAULT_SOURCING_INTERVAL_SECONDS,
) -> datetime:
    """Spread schedule starts evenly across the interval so they don't all fire at once."""
    if total <= 0:
        return now + timedelta(seconds=interval_seconds)
    stagger_seconds = (interval_seconds // total) * index
    return now + timedelta(seconds=stagger_seconds)


def default_sources_for_thesis(thesis: Thesis) -> List[SourceConfig]:
    """Generate LinkedIn + Twitter keyword sources for a thesis."""
    sectors = ", ".join(thesis.sectors)
    geographies = ", ".join(thesis.geographies)
    return [
        SourceConfig(
            platform="linkedin",
            keywords=f"{sectors} founders {geographies}",
        ),
        SourceConfig(
            platform="twitter",
            keywords=f"{sectors} startup founder {geographies}",
        ),
    ]


# ---------------------------------------------------------------------------
# Sample founders and opportunities derived from frontend demo data.
# ---------------------------------------------------------------------------

SAMPLE_FOUNDERS: List[Dict[str, Any]] = [
    {
        "id": "demo_fnd_talent_a",
        "name": "Alex Rivera",
        "email": "alex.rivera.demo@founderos.example",
        "current_company": "ML Code Review",
        "role": "Solo builder / ML engineer",
        "location": "Berlin, Germany",
        "linkedin_url": "https://linkedin.example/in/alexrivera",
        "github_url": "https://github.com/arivera/ml-code-review",
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
    },
]


SAMPLE_OPPORTUNITIES: List[Dict[str, Any]] = [
    {
        "opportunity_id": "demo_opp_cold_start",
        "founder_id": "demo_fnd_talent_a",
        "founder_score": 62,
        "founder_confidence": 0.55,
        "market_posture": "neutral",
        "market_confidence": 0.4,
        "idea_vs_market_posture": "weak, pivotable",
        "idea_vs_market_confidence": 0.45,
        "next_founder_action": "Run structured cold-start assessment.",
    },
    {
        "opportunity_id": "demo_opp_founder_spike",
        "founder_id": "demo_fnd_founder_b",
        "founder_score": 78,
        "founder_confidence": 0.68,
        "market_posture": "neutral",
        "market_confidence": 0.45,
        "idea_vs_market_posture": "weak, pivotable",
        "idea_vs_market_confidence": 0.5,
        "next_founder_action": "Run customer reference and team-scaling review.",
    },
    {
        "opportunity_id": "demo_opp_contradictory_traction",
        "founder_id": "demo_fnd_founder_c",
        "founder_score": 65,
        "founder_confidence": 0.5,
        "market_posture": "neutral",
        "market_confidence": 0.55,
        "idea_vs_market_posture": "plausible, unvalidated",
        "idea_vs_market_confidence": 0.55,
        "next_founder_action": "Resolve revenue/customer adoption contradiction with bank statement or customer references.",
    },
]


SAMPLE_POOL_ITEMS: List[Dict[str, Any]] = [
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
        "status": "recommended",
    },
]
