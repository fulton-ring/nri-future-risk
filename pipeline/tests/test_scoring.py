import numpy as np
import pandas as pd
import pytest

from fri_pipeline.scoring import classify, display_score, projected_rating, risk_score, thresholds


def test_boundary_ties_and_missing_values():
    assert classify(pd.Series([1, 1.0001, 2, 5, np.nan]), [1, 2, 3, 4]).tolist()[:4] == [
        "Very Low",
        "Relatively Low",
        "Relatively Low",
        "Very High",
    ]
    assert pd.isna(classify(pd.Series([np.nan]), [1, 2, 3, 4]).iloc[0])
    assert classify(pd.Series([1, 1.01]), [1, 1, 1.3, 2.59]).tolist() == [
        "Very Low",
        "Relatively Moderate",
    ]


def test_zero_ties_participate_in_rank_and_four_significant_digits():
    assert risk_score(pd.Series([0, 0, 100, np.nan])).iloc[:3].tolist() == [50, 50, 100]
    assert display_score(pd.Series([7.397391, 86.7345])).tolist() == [7.397, 86.73]


def test_special_statuses_survive_projection():
    baseline = pd.Series(["No Expected Annual Losses", "Insufficient Data", "Very Low"])
    assert projected_rating(pd.Series([0, np.nan, 1]), baseline, [1, 2, 3, 4]).tolist() == [
        "No Rating",
        "Not Applicable",
        "Very Low",
    ]


def test_thresholds_require_the_complete_baseline():
    with pytest.raises(ValueError, match="threshold"):
        thresholds(pd.Series([1, 2]), pd.Series(["Very Low", "Relatively Low"]))
