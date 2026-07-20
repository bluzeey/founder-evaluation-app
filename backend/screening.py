import math
from typing import NamedTuple, Optional

from models import FounderScreeningProfile, RecommendationTrigger


class RecommendationEvaluation(NamedTuple):
    recommended: bool
    trigger: RecommendationTrigger
    reason: str


def _validate_score(name: str, value: Optional[int]) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer between 0 and 100")
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer between 0 and 100")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")


def validate_screening_scores(
    founder_score: Optional[int],
    vision_product_score: Optional[int],
    differentiation_score: Optional[int],
    traction_score: Optional[int],
) -> None:
    _validate_score("founder_score", founder_score)
    _validate_score("vision_product_score", vision_product_score)
    _validate_score("differentiation_score", differentiation_score)
    _validate_score("traction_score", traction_score)


def evaluate_recommendation(
    founder_score: Optional[int],
    vision_product_score: Optional[int],
    differentiation_score: Optional[int],
    traction_score: Optional[int],
) -> RecommendationEvaluation:
    validate_screening_scores(
        founder_score,
        vision_product_score,
        differentiation_score,
        traction_score,
    )

    scores = [
        founder_score,
        vision_product_score,
        differentiation_score,
        traction_score,
    ]
    if any(score is None for score in scores):
        return RecommendationEvaluation(
            False,
            RecommendationTrigger.INCOMPLETE_EVALUATION,
            "Associate screen is incomplete because one or more scores are missing.",
        )

    numeric_scores = [score for score in scores if score is not None]
    one_high = any(score > 75 for score in numeric_scores)
    above_50_count = sum(score > 50 for score in numeric_scores)
    two_above_50 = above_50_count >= 2

    if one_high and two_above_50:
        return RecommendationEvaluation(
            True,
            RecommendationTrigger.ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50,
            "Recommended because at least one score is greater than 75 and at least two scores are greater than 50.",
        )
    if one_high:
        return RecommendationEvaluation(
            True,
            RecommendationTrigger.ONE_SCORE_GT_75,
            "Recommended because at least one score is greater than 75.",
        )
    if two_above_50:
        return RecommendationEvaluation(
            True,
            RecommendationTrigger.TWO_SCORES_GT_50,
            "Recommended because at least two scores are greater than 50.",
        )
    return RecommendationEvaluation(
        False,
        RecommendationTrigger.NOT_RECOMMENDED,
        "Not recommended because no score is greater than 75 and fewer than two scores are greater than 50.",
    )


def screening_sort_key(profile: FounderScreeningProfile) -> tuple:
    evaluation = evaluate_recommendation(
        profile.founder_score,
        profile.vision_product_score,
        profile.differentiation_score,
        profile.traction_score,
    )
    scores = [
        score
        for score in [
            profile.founder_score,
            profile.vision_product_score,
            profile.differentiation_score,
            profile.traction_score,
        ]
        if score is not None
    ]
    trigger_rank = {
        RecommendationTrigger.ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50: 0,
        RecommendationTrigger.ONE_SCORE_GT_75: 1,
        RecommendationTrigger.TWO_SCORES_GT_50: 2,
        RecommendationTrigger.NOT_RECOMMENDED: 3,
        RecommendationTrigger.INCOMPLETE_EVALUATION: 4,
    }[evaluation.trigger]
    highest_score = max(scores) if scores else -1
    above_50_count = sum(score > 50 for score in scores)
    evidence_confidence = profile.evidence_confidence if profile.evidence_confidence is not None else -1.0
    evidence_coverage = profile.evidence_coverage if profile.evidence_coverage is not None else -1.0
    return (
        trigger_rank,
        -highest_score,
        -above_50_count,
        -evidence_confidence,
        -evidence_coverage,
    )
