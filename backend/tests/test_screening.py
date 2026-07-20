import math
import pytest

from models import RecommendationTrigger
from screening import evaluate_recommendation, validate_screening_scores


@pytest.mark.parametrize(
    ("scores", "recommended", "trigger"),
    [
        ((76, 0, 0, 0), True, RecommendationTrigger.ONE_SCORE_GT_75),
        ((75, 51, 49, 49), True, RecommendationTrigger.TWO_SCORES_GT_50),
        ((51, 51, 0, 0), True, RecommendationTrigger.TWO_SCORES_GT_50),
        ((50, 50, 100, 0), True, RecommendationTrigger.ONE_SCORE_GT_75),
        ((50, 50, 75, 0), False, RecommendationTrigger.NOT_RECOMMENDED),
        ((90, 80, 40, 40), True, RecommendationTrigger.ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50),
        ((None, 90, 90, 90), False, RecommendationTrigger.INCOMPLETE_EVALUATION),
    ],
)
def test_evaluate_recommendation_boundaries(scores, recommended, trigger):
    result = evaluate_recommendation(*scores)
    assert result.recommended is recommended
    assert result.trigger == trigger


@pytest.mark.parametrize(
    "scores",
    [
        (76, 0, 0, 0),
        (0, 76, 0, 0),
        (0, 0, 76, 0),
        (0, 0, 0, 76),
        (51, 51, 0, 0),
        (51, 0, 51, 0),
        (51, 0, 0, 51),
        (0, 51, 51, 0),
        (0, 51, 0, 51),
        (0, 0, 51, 51),
    ],
)
def test_recommendation_is_order_independent(scores):
    assert evaluate_recommendation(*scores).recommended is True


@pytest.mark.parametrize("value", [-1, 101, True, 99.5, float("nan")])
def test_validate_screening_scores_rejects_invalid_values(value):
    with pytest.raises((ValueError, TypeError)):
        validate_screening_scores(value, 0, 0, 0)
