from __future__ import annotations

import numpy as np
import pytest

from ai_risk.metrics import compute_thresholded_metrics, fixed_fpr_operating_points


def test_fixed_fpr_operating_points_select_thresholds_from_reference_and_evaluate_on_holdout():
    reference_y = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=int)
    reference_scores = np.array([0.05, 0.10, 0.20, 0.30, 0.80, 0.85, 0.90, 0.95], dtype=float)
    evaluation_y = np.array([0, 0, 0, 1, 1, 1], dtype=int)
    evaluation_scores = np.array([0.04, 0.09, 0.79, 0.81, 0.88, 0.96], dtype=float)

    result = fixed_fpr_operating_points(
        reference_y,
        reference_scores,
        evaluation_y_true=evaluation_y,
        evaluation_scores=evaluation_scores,
        fpr_targets=[0.01, 0.25],
    )

    assert list(result["target_fpr"]) == [0.01, 0.25]
    assert (result["reference_fpr"] <= result["target_fpr"]).all()
    assert result.loc[0, "realized_fpr"] == 0.0
    assert result.loc[0, "detection_rate"] == 1.0
    assert result.loc[1, "threshold"] <= result.loc[0, "threshold"]
    # New imbalance-aware columns must be present
    for col in ["tn", "fp", "fn", "tp", "specificity", "balanced_accuracy", "mcc", "false_alarms_per_1000_benign"]:
        assert col in result.columns, f"Column '{col}' missing from fixed_fpr_operating_points output"


def test_thresholded_metrics_include_imbalance_sensitive_fields():
    # y=0 → benign, y=1 → malicious
    # threshold=0.5: scores [0.1,0.8,0.2] → predictions [0,1,0] for benign (TN=2, FP=1)
    #                scores [0.9,0.7] → predictions [1,1] for malicious (TP=2, FN=0)
    y_true = np.array([0, 0, 0, 1, 1])
    scores = np.array([0.1, 0.8, 0.2, 0.9, 0.7])
    m = compute_thresholded_metrics(y_true, scores, threshold=0.5)

    assert m.tn == 2
    assert m.fp == 1
    assert m.fn == 0
    assert m.tp == 2

    assert m.n_samples == 5
    assert m.n_benign == 3      # TN + FP
    assert m.n_malicious == 2   # TP + FN

    assert pytest.approx(m.specificity, rel=1e-6) == 2 / 3
    assert pytest.approx(m.benign_recall, rel=1e-6) == 2 / 3
    assert pytest.approx(m.false_alarms_per_1000_benign, rel=1e-3) == 1000 / 3
    assert pytest.approx(m.prevalence, rel=1e-6) == 2 / 5
    assert 0.0 <= m.mcc <= 1.0
    assert 0.0 <= m.balanced_accuracy <= 1.0
    # balanced_accuracy = (recall + specificity) / 2 = (1.0 + 2/3) / 2 = 5/6
    assert pytest.approx(m.balanced_accuracy, rel=1e-6) == 5 / 6
