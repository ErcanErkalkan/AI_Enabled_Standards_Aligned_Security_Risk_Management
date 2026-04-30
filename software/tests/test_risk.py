from __future__ import annotations

import numpy as np
import pandas as pd

from ai_risk.risk import compute_risk_frame, residual_risk_from_controls


def test_compute_risk_frame_has_expected_columns():
    frame = pd.DataFrame(
        {
            "asset_value_raw": [100.0, 200.0, 400.0],
            "cvss_exploitability": [0.1, 0.4, 0.8],
            "cvss_c": [0.2, 0.4, 0.6],
            "cvss_i": [0.2, 0.5, 0.6],
            "cvss_a": [0.1, 0.5, 0.7],
            "hf_failure_ratio": [0.1, 0.2, 0.3],
            "hf_policy_violations": [0.1, 0.2, 0.3],
            "hf_training_gap": [0.1, 0.2, 0.3],
        }
    )
    risk_frame = compute_risk_frame(frame, likelihood_signal=np.array([0.1, 0.5, 0.9]), w_h=0.2)
    assert {"AV", "HF", "EP", "IL", "BR", "expected_loss"}.issubset(risk_frame.columns)
    assert np.all(risk_frame["BR"] >= 0.0)


def test_residual_risk_decreases_when_more_controls_are_applied():
    base_risk = np.array([0.4, 0.6, 0.8])
    without_controls = residual_risk_from_controls(base_risk, [], hf_reduction=0.0)
    with_controls = residual_risk_from_controls(base_risk, [0.10, 0.20], hf_reduction=0.05)
    assert np.all(with_controls < without_controls)


def test_compute_risk_frame_does_not_reduce_technical_impact_when_hf_is_unavailable():
    frame = pd.DataFrame(
        {
            "asset_value_raw": [100.0, 100.0],
            "cvss_exploitability": [0.4, 0.4],
            "cvss_c": [0.4, 0.4],
            "cvss_i": [0.3, 0.3],
            "cvss_a": [0.2, 0.2],
            "hf_failure_ratio": [0.0, 0.0],
            "hf_policy_violations": [0.0, 0.0],
            "hf_training_gap": [0.0, 0.0],
            "hf_source": ["HF:none", "HF:none"],
        }
    )

    risk_without_hf = compute_risk_frame(frame, likelihood_signal=np.array([0.2, 0.2]), w_h=0.0)
    risk_with_missing_hf = compute_risk_frame(frame, likelihood_signal=np.array([0.2, 0.2]), w_h=0.3)

    assert np.allclose(risk_without_hf["IL"], risk_with_missing_hf["IL"])
