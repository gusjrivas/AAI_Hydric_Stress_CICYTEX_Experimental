import pandas as pd

from experiment_runner.cicytex.causal_ensemble import _metrics


def test_metrics_preserve_undefined_values_instead_of_inventing_zero():
    rows = pd.DataFrame({"observed_label": [0, 0], "score": [0.1, 0.2], "alert": [False, False]})
    result = _metrics(rows)
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["f1"] is None
    assert result["mcc"] is None


def test_ensemble_score_is_arithmetic_mean():
    scores = pd.DataFrame({"lr": [0.2], "rf": [0.7], "hgb": [0.6]})
    assert scores.mean(axis=1).iloc[0] == 0.5
