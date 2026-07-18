import uuid
from typing import Any, List

from models import Dimension, EvidenceItem, EvidenceStatus, EvidenceType, Founder

_DIMENSION_MAP = {d.value: d for d in Dimension}
_EVIDENCE_TYPE_MAP = {e.value: e for e in EvidenceType}
_EVIDENCE_STATUS_MAP = {e.value: e for e in EvidenceStatus}


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, value))


def evidence_from_llm(founder_id: str, item: dict[str, Any]) -> EvidenceItem:
    """Coerce one LLM evidence dict into a valid EvidenceItem."""
    dimension = _DIMENSION_MAP.get(item.get("dimension", ""), Dimension.CLAIM_RELIABILITY)
    evidence_type = _EVIDENCE_TYPE_MAP.get(
        item.get("evidence_type", ""), EvidenceType.UNVERIFIED_PROXY
    )
    polarity = _EVIDENCE_STATUS_MAP.get(item.get("polarity", ""), EvidenceStatus.UNKNOWN)
    status = _EVIDENCE_STATUS_MAP.get(item.get("status", ""), polarity)

    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        founder_id=founder_id,
        dimension=dimension,
        observation=item.get("observation", ""),
        source_type=item.get("source_type", "web_search"),
        source_id=f"ws_{uuid.uuid4().hex[:8]}",
        source_locator=item.get("source_locator", ""),
        evidence_type=evidence_type,
        rubric_level=max(0, min(4, int(item.get("rubric_level", 2) or 2))),
        source_trust=_clamp(float(item.get("source_trust", 0.5) or 0.5)),
        task_relevance=_clamp(float(item.get("task_relevance", 0.5) or 0.5)),
        recency_factor=_clamp(float(item.get("recency_factor", 0.5) or 0.5)),
        independence_group=item.get("independence_group", "web_search"),
        polarity=polarity,
        status=status,
        counter_evidence=item.get("counter_evidence") or None,
        unknowns=item.get("unknowns") or None,
    )


def create_founder_from_research(
    profile: dict[str, Any],
    summary: str,
    sources: List[str],
) -> Founder:
    """Create a Founder record from the LLM-extracted profile."""
    return Founder(
        id=f"fnd_{uuid.uuid4().hex[:8]}",
        name=profile.get("name", "Unknown") or "Unknown",
        email=profile.get("email", "") or "",
        current_company=profile.get("current_company"),
        role=profile.get("role"),
        location=profile.get("location"),
        linkedin_url=profile.get("linkedin_url"),
        github_url=profile.get("github_url"),
        ai_research_summary=summary or None,
        ai_research_sources=sources or [],
    )
