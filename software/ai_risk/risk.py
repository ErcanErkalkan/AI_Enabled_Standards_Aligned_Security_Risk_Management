from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


@dataclass(frozen=True)
class RiskWeights:
    confidentiality: float = 0.30
    integrity: float = 0.25
    availability: float = 0.25
    human_factor: float = 0.20


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def normalize_asset_values(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    value_min = values.min()
    value_max = values.max()
    if np.isclose(value_max, value_min):
        return np.ones_like(values)
    return (values - value_min) / (value_max - value_min)


def synthesize_human_factor(frame: pd.DataFrame) -> np.ndarray:
    hf = (
        0.45 * frame["hf_failure_ratio"].to_numpy(dtype=float)
        + 0.30 * frame["hf_policy_violations"].to_numpy(dtype=float)
        + 0.25 * frame["hf_training_gap"].to_numpy(dtype=float)
    )
    return np.clip(hf, 0.0, 1.0)


def human_factor_available(frame: pd.DataFrame) -> np.ndarray:
    if "hf_source" in frame.columns:
        source = frame["hf_source"].fillna("HF:none").astype(str).to_numpy()
        return source != "HF:none"
    return frame[["hf_failure_ratio", "hf_policy_violations", "hf_training_gap"]].notna().all(axis=1).to_numpy(dtype=bool)


def impact_level(frame: pd.DataFrame, w_h: float, weights: RiskWeights | None = None) -> np.ndarray:
    weights = weights or RiskWeights(human_factor=w_h)
    technical_total = weights.confidentiality + weights.integrity + weights.availability
    if technical_total + w_h <= 0:
        raise ValueError("Risk weights must have positive total mass.")
    hf_mask = human_factor_available(frame).astype(float)
    hf_weight = np.clip(w_h * hf_mask, 0.0, 1.0)
    tech_scale = 1.0 - hf_weight
    technical_cia = (
        weights.confidentiality / technical_total * frame["cvss_c"].to_numpy(dtype=float)
        + weights.integrity / technical_total * frame["cvss_i"].to_numpy(dtype=float)
        + weights.availability / technical_total * frame["cvss_a"].to_numpy(dtype=float)
    )
    hf = synthesize_human_factor(frame)
    impact = tech_scale * technical_cia + hf_weight * hf
    return np.clip(impact, 0.0, 1.0)


def event_probability(likelihood_signal: np.ndarray, exploitability: np.ndarray, alpha: float = 1.1, beta: float = 1.0) -> np.ndarray:
    return sigmoid(alpha * np.asarray(likelihood_signal, dtype=float) + beta * np.asarray(exploitability, dtype=float))


def fit_event_probability_parameters(likelihood_signal: np.ndarray, exploitability: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    X = np.column_stack([np.asarray(likelihood_signal, dtype=float), np.asarray(exploitability, dtype=float)])
    y = np.asarray(labels, dtype=int)
    if len(np.unique(y)) < 2:
        return 1.1, 1.0
    model = LogisticRegression(fit_intercept=False, solver="lbfgs", max_iter=1000)
    model.fit(X, y)
    alpha, beta = model.coef_[0]
    return float(alpha), float(beta)


def compute_risk_frame(meta: pd.DataFrame, likelihood_signal: np.ndarray, w_h: float, alpha: float = 1.1, beta: float = 1.0) -> pd.DataFrame:
    frame = meta.copy()
    frame["AV"] = normalize_asset_values(frame["asset_value_raw"].to_numpy(dtype=float))
    frame["HF"] = synthesize_human_factor(frame)
    frame["EP"] = event_probability(likelihood_signal, frame["cvss_exploitability"].to_numpy(dtype=float), alpha=alpha, beta=beta)
    frame["IL"] = impact_level(frame, w_h=w_h)
    frame["BR"] = frame["AV"] * frame["EP"] * frame["IL"]
    frame["expected_loss"] = frame["asset_value_raw"] * frame["EP"] * frame["IL"]
    return frame


def residual_risk(base_risk: np.ndarray, effectiveness: np.ndarray, hf_reduction: float = 0.0) -> np.ndarray:
    return np.asarray(base_risk, dtype=float) * np.clip(1.0 - hf_reduction, 0.0, 1.0) * np.prod(1.0 - np.asarray(effectiveness, dtype=float))


def residual_risk_from_controls(base_risk: np.ndarray, control_effectiveness: list[float], hf_reduction: float = 0.0) -> np.ndarray:
    multiplier = np.prod([1.0 - value for value in control_effectiveness], dtype=float) if control_effectiveness else 1.0
    return np.asarray(base_risk, dtype=float) * max(0.0, 1.0 - hf_reduction) * multiplier


def risk_reduction_level(base_risk: np.ndarray, residual: np.ndarray) -> np.ndarray:
    base_risk = np.asarray(base_risk, dtype=float)
    residual = np.asarray(residual, dtype=float)
    safe_base = np.where(base_risk == 0, 1.0, base_risk)
    return np.clip((base_risk - residual) / safe_base, 0.0, 1.0)


def portfolio_budget(expected_loss: float, gamma: float = 0.37) -> float:
    return gamma * expected_loss


def compute_three_year_tco(capex: float, annual_opex: float, annual_hidden: float) -> float:
    return float(capex + 3.0 * annual_opex + 3.0 * annual_hidden)
