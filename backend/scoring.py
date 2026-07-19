import logging
from typing import List
from datetime import datetime, timezone
from collections import defaultdict
from models import (
    EvidenceItem,
    Dimension,
    DimensionBreakdown,
    ScoreSnapshot,
    DIMENSION_WEIGHTS,
    EVIDENCE_TYPE_STRENGTH,
    REQUIRED_EFFECTIVE_WEIGHT,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)


def _effective_weight(item: EvidenceItem) -> float:
    return (
        EVIDENCE_TYPE_STRENGTH[item.evidence_type]
        * item.source_trust
        * item.task_relevance
        * item.recency_factor
    )


def _independence_factor(items: List[EvidenceItem]) -> float:
    groups = {item.independence_group for item in items}
    n = len(groups)
    if n >= 3:
        return 1.0
    if n == 2:
        return 0.85
    if n == 1:
        return 0.65
    return 1.0


def calculate_dimension(dimension: Dimension, items: List[EvidenceItem]) -> DimensionBreakdown:
    if not items:
        return DimensionBreakdown(
            dimension=dimension,
            weight=DIMENSION_WEIGHTS[dimension],
            raw_score=50.0,
            adjusted_score=50.0,
            confidence=0.0,
            evidence_band_low=40.0,
            evidence_band_high=60.0,
            coverage=0.0,
            evidence_count=0,
            contradiction_count=0,
            unknown=True,
            positive_evidence=[],
            counter_evidence=[],
            unknowns=["No evidence observed for this dimension."],
            next_test=f"Assign a structured assessment module for {dimension.value}.",
        )

    # Cap any single item at 30% of total effective weight per dimension rule.
    eff_weights = []
    for item in items:
        ew = _effective_weight(item)
        total_others = sum(_effective_weight(i) for i in items if i.id != item.id)
        if total_others > 0 and ew / (ew + total_others) > 0.30:
            ew = 0.30 * total_others / 0.70
        eff_weights.append(ew)

    weighted_sum = sum(
        (item.rubric_level / 4.0 * 100) * ew for item, ew in zip(items, eff_weights)
    )
    total_weight = sum(eff_weights)
    raw_score = weighted_sum / total_weight if total_weight > 0 else 50.0

    # Confidence components
    coverage = min(1.0, total_weight / REQUIRED_EFFECTIVE_WEIGHT)

    groups = {item.independence_group for item in items}
    source_diversity = min(1.0, len(groups) / 3.0)

    contradiction_weights = sum(
        ew for item, ew in zip(items, eff_weights) if item.status == EvidenceStatus.CONTRADICTORY
    )
    contradiction_rate = contradiction_weights / total_weight if total_weight > 0 else 0.0
    contradiction_factor = 1.0 - min(0.5, contradiction_rate)

    confidence = coverage * (0.70 + 0.30 * source_diversity) * contradiction_factor

    # Hard rules from PRD
    # AI chat / estimates alone cannot create confidence above 0.60
    chat_only = all(
        item.evidence_type.value
        in ("structured_simulation", "structured_interview", "self_reported", "inferred_estimate")
        for item in items
    )
    if chat_only:
        confidence = min(confidence, 0.60)

    # Confidence above 0.65 requires at least one non-chat artifact or independently verified source.
    has_non_chat = any(
        item.evidence_type.value
        in ("verified_outcome", "work_sample", "repeated_behavior", "inspected_artifact")
        for item in items
    )
    if confidence > 0.65 and not has_non_chat:
        confidence = 0.65

    # Confidence above 0.80 requires evidence from at least three independent source groups.
    if confidence > 0.80 and len(groups) < 3:
        confidence = 0.80

    # Shrinkage toward neutral prior
    adjusted_score = 50.0 + confidence * (raw_score - 50.0)

    band_width = 20.0 * (1.0 - confidence)
    low = max(0.0, adjusted_score - band_width)
    high = min(100.0, adjusted_score + band_width)

    positive_evidence = [
        item.observation for item in items if item.status == EvidenceStatus.POSITIVE
    ]
    counter_evidence = [
        item.observation for item in items if item.status in (EvidenceStatus.NEGATIVE, EvidenceStatus.CONTRADICTORY)
    ]
    unknowns = []
    if coverage < 1.0:
        unknowns.append("Coverage is incomplete; additional evidence will improve confidence.")
    unknowns.extend([item.unknowns for item in items if item.unknowns])

    next_tests = [item.unknowns for item in items if item.unknowns]
    next_test = next_tests[0] if next_tests else None

    return DimensionBreakdown(
        dimension=dimension,
        weight=DIMENSION_WEIGHTS[dimension],
        raw_score=round(raw_score, 2),
        adjusted_score=round(adjusted_score, 2),
        confidence=round(confidence, 4),
        evidence_band_low=round(low, 2),
        evidence_band_high=round(high, 2),
        coverage=round(coverage, 4),
        evidence_count=len(items),
        contradiction_count=sum(1 for item in items if item.status == EvidenceStatus.CONTRADICTORY),
        unknown=False,
        positive_evidence=positive_evidence,
        counter_evidence=counter_evidence,
        unknowns=unknowns,
        next_test=next_test,
    )


def calculate_founder_score(
    founder_id: str,
    evidence_items: List[EvidenceItem],
    previous_snapshot: ScoreSnapshot = None,
) -> ScoreSnapshot:
    logger.info(
        "scoring.calculate_founder_score.start founder_id=%s evidence=%s",
        founder_id,
        len(evidence_items),
    )
    by_dimension = defaultdict(list)
    for item in evidence_items:
        by_dimension[item.dimension].append(item)

    breakdowns = []
    weighted_score = 0.0
    total_weight_used = 0.0
    confidences = []
    coverages = []

    for dim in Dimension:
        dim_items = by_dimension.get(dim, [])
        bd = calculate_dimension(dim, dim_items)
        breakdowns.append(bd)
        if not bd.unknown:
            weighted_score += bd.adjusted_score * bd.weight
            total_weight_used += bd.weight
        confidences.append(bd.confidence)
        coverages.append(bd.coverage)

    founder_score = weighted_score / total_weight_used if total_weight_used > 0 else 50.0
    overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    evidence_coverage = sum(coverages) / len(coverages) if coverages else 0.0

    band_width = 20.0 * (1.0 - overall_confidence)
    low = max(0.0, founder_score - band_width)
    high = min(100.0, founder_score + band_width)

    trend = 0
    if previous_snapshot:
        trend = round(founder_score - previous_snapshot.founder_score)

    snapshot_id = f"snap_{founder_id}_{datetime.now(timezone.utc).isoformat()}"

    change_explanation = None
    if previous_snapshot:
        change_explanation = (
            f"Score changed from {previous_snapshot.founder_score} to {round(founder_score, 2)}. "
            f"Evidence items: {len(evidence_items)} total."
        )

    logger.info(
        "scoring.calculate_founder_score.end founder_id=%s score=%s confidence=%s coverage=%s",
        founder_id,
        round(founder_score, 2),
        round(overall_confidence, 4),
        round(evidence_coverage, 4),
    )
    return ScoreSnapshot(
        id=snapshot_id,
        founder_id=founder_id,
        rubric_version="founder_score_v1",
        prompt_version="gap_planner_v1",
        model_version="deterministic_engine_v1",
        created_at=datetime.now(timezone.utc),
        founder_score=round(founder_score, 2),
        evidence_band_low=round(low, 2),
        evidence_band_high=round(high, 2),
        overall_confidence=round(overall_confidence, 4),
        evidence_coverage=round(evidence_coverage, 4),
        trend=trend,
        dimension_breakdowns=breakdowns,
        evidence_items=evidence_items,
        change_explanation=change_explanation,
    )
