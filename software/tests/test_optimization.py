from __future__ import annotations

import numpy as np
import pandas as pd

from ai_risk.optimization.portfolio import evaluate_portfolio, run_greedy


def test_greedy_portfolio_respects_budget():
    control_frame = pd.DataFrame(
        {
            "control_id": ["c1", "c2", "c3"],
            "capex": [10.0, 15.0, 100.0],
            "opex": [2.0, 3.0, 7.0],
            "ai_opex": [1.0, 1.0, 1.0],
            "effectiveness": [0.10, 0.20, 0.50],
            "detect_gain": [0.01, 0.02, 0.03],
            "fpr_delta": [0.0, -0.01, 0.02],
            "hf_delta": [0.0, 0.02, 0.01],
        }
    )
    frontier, _ = run_greedy(control_frame, np.array([0.3, 0.4, 0.5]), base_detection_rate=0.90, base_fpr=0.05, budget=30.0)
    assert not frontier.empty
    assert float(frontier.iloc[0]["capex"]) <= 30.0
