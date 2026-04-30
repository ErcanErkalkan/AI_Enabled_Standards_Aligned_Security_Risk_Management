from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


def cliffs_delta(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    comparisons = 0
    score = 0
    for value_left in left:
        for value_right in right:
            score += np.sign(value_left - value_right)
            comparisons += 1
    return float(score / max(comparisons, 1))


def pairwise_wilcoxon_table(metric_series: dict[str, np.ndarray], metric_name: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for left_name, right_name in combinations(sorted(metric_series), 2):
        left = np.asarray(metric_series[left_name], dtype=float)
        right = np.asarray(metric_series[right_name], dtype=float)
        if np.allclose(left, right):
            stat, pvalue = 0.0, 1.0
        else:
            try:
                stat, pvalue = wilcoxon(left, right, zero_method="wilcox", alternative="two-sided")
            except ValueError:
                stat, pvalue = 0.0, 1.0
        if np.isnan(pvalue):
            stat, pvalue = 0.0, 1.0
        rows.append(
            {
                "metric": metric_name,
                "model_a": left_name,
                "model_b": right_name,
                "wilcoxon_stat": float(stat),
                "p_value": float(pvalue),
                "cliffs_delta": cliffs_delta(left, right),
            }
        )
    return pd.DataFrame(rows)
