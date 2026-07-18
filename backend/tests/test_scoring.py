import pytest
from datetime import datetime, timezone
from models import EvidenceItem, Dimension, EvidenceType, EvidenceStatus
from scoring import calculate_founder_score


def make_item(**kwargs):
    defaults = {
        "id": "ev_test",
        "founder_id": "fnd_test",
        "dimension": Dimension.EXECUTION,
        "observation": "Test observation",
        "source_type": "test",
        "source_id": "src_test",
        "source_locator": "turn_1",
        "evidence_type": EvidenceType.STRUCTURED_SIMULATION,
        "rubric_level": 3,
        "source_trust": 0.8,
        "task_relevance": 0.9,
        "recency_factor": 1.0,
        "independence_group": "grp_1",
        "polarity": EvidenceStatus.POSITIVE,
        "status": EvidenceStatus.POSITIVE,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return EvidenceItem(**defaults)


def test_missing_dimension_is_unknown():
    snapshot = calculate_founder_score("fnd_test", [])
    execution = next(d for d in snapshot.dimension_breakdowns if d.dimension == Dimension.EXECUTION)
    assert execution.unknown is True
    assert execution.adjusted_score == 50.0
    assert execution.confidence == 0.0


def test_single_item_cap():
    # One strong item should not produce extreme confidence or score.
    item = make_item(rubric_level=4, evidence_type=EvidenceType.STRUCTURED_SIMULATION)
    snapshot = calculate_founder_score("fnd_test", [item])
    execution = next(d for d in snapshot.dimension_breakdowns if d.dimension == Dimension.EXECUTION)
    assert execution.adjusted_score < 90


def test_chat_only_confidence_cap():
    items = [
        make_item(dimension=Dimension.CUSTOMER_SELLING, rubric_level=4, independence_group="g1"),
        make_item(dimension=Dimension.CUSTOMER_SELLING, rubric_level=4, independence_group="g2"),
        make_item(dimension=Dimension.CUSTOMER_SELLING, rubric_level=4, independence_group="g3"),
    ]
    snapshot = calculate_founder_score("fnd_test", items)
    cs = next(d for d in snapshot.dimension_breakdowns if d.dimension == Dimension.CUSTOMER_SELLING)
    assert cs.confidence <= 0.60


def test_verified_source_bypasses_chat_cap():
    items = [
        make_item(
            dimension=Dimension.CUSTOMER_SELLING,
            evidence_type=EvidenceType.VERIFIED_OUTCOME,
            rubric_level=4,
            independence_group="g1",
        ),
        make_item(
            dimension=Dimension.CUSTOMER_SELLING,
            evidence_type=EvidenceType.VERIFIED_OUTCOME,
            rubric_level=4,
            independence_group="g2",
        ),
        make_item(
            dimension=Dimension.CUSTOMER_SELLING,
            evidence_type=EvidenceType.VERIFIED_OUTCOME,
            rubric_level=4,
            independence_group="g3",
        ),
    ]
    snapshot = calculate_founder_score("fnd_test", items)
    cs = next(d for d in snapshot.dimension_breakdowns if d.dimension == Dimension.CUSTOMER_SELLING)
    assert cs.confidence > 0.60


def test_contradiction_reduces_confidence():
    items = [
        make_item(dimension=Dimension.CLAIM_RELIABILITY, rubric_level=4, independence_group="g1"),
        make_item(
            dimension=Dimension.CLAIM_RELIABILITY,
            rubric_level=1,
            status=EvidenceStatus.CONTRADICTORY,
            independence_group="g2",
        ),
    ]
    snapshot = calculate_founder_score("fnd_test", items)
    cr = next(d for d in snapshot.dimension_breakdowns if d.dimension == Dimension.CLAIM_RELIABILITY)
    assert cr.confidence < 1.0
    assert cr.contradiction_count == 1
