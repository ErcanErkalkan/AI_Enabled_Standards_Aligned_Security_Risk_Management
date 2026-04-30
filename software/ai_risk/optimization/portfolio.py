from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.operators.crossover.pntx import TwoPointCrossover
from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.operators.sampling.rnd import BinaryRandomSampling
from pymoo.optimize import minimize

from ai_risk.risk import compute_three_year_tco, portfolio_budget, residual_risk_from_controls

PORTFOLIO_RESULT_COLUMNS = [
    "method",
    "selected_controls",
    "mean_residual_risk",
    "p90_residual_risk",
    "capex",
    "annual_control_opex",
    "annual_ai_opex",
    "annual_opex",
    "tco_3y",
    "detection_rate",
    "false_positive_rate",
    "hf_reduction",
]

DEFAULT_RECOMMENDATION_WEIGHTS = {
    "mean_residual_risk": 0.40,
    "tco_3y": 0.25,
    "false_positive_rate": 0.20,
    "detection_rate": 0.15,
}


@dataclass
class PortfolioEvaluation:
    selected_controls: list[str]
    mean_residual_risk: float
    p90_residual_risk: float
    capex: float
    annual_control_opex: float
    annual_ai_opex: float
    annual_opex: float
    tco_3y: float
    detection_rate: float
    false_positive_rate: float
    hf_reduction: float


def load_control_catalog(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return frame


def evaluate_portfolio(
    control_frame: pd.DataFrame,
    selection_mask: np.ndarray,
    base_risk: np.ndarray,
    base_detection_rate: float,
    base_fpr: float,
) -> PortfolioEvaluation:
    selected = control_frame.loc[np.asarray(selection_mask, dtype=bool)].copy()
    effectiveness = selected["effectiveness"].to_numpy(dtype=float).tolist()
    hf_reduction = float(np.clip(selected["hf_delta"].sum(), 0.0, 0.35))
    residual = residual_risk_from_controls(base_risk, effectiveness, hf_reduction=hf_reduction)
    detection_rate = float(np.clip(base_detection_rate + selected["detect_gain"].sum(), 0.0, 1.0))
    false_positive_rate = float(np.clip(base_fpr + selected["fpr_delta"].sum(), 0.0, 1.0))
    capex = float(selected["capex"].sum())
    annual_control_opex = float(selected["opex"].sum())
    annual_ai_opex = float(selected["ai_opex"].sum())
    annual_opex = annual_control_opex + annual_ai_opex
    tco_3y = compute_three_year_tco(capex=capex, annual_opex=annual_opex, annual_hidden=0.0)
    return PortfolioEvaluation(
        selected_controls=selected["control_id"].tolist(),
        mean_residual_risk=float(np.mean(residual)),
        p90_residual_risk=float(np.quantile(residual, 0.90)),
        capex=capex,
        annual_control_opex=annual_control_opex,
        annual_ai_opex=annual_ai_opex,
        annual_opex=annual_opex,
        tco_3y=tco_3y,
        detection_rate=detection_rate,
        false_positive_rate=false_positive_rate,
        hf_reduction=hf_reduction,
    )


def _evaluation_to_row(method_name: str, evaluation: PortfolioEvaluation) -> dict[str, object]:
    return {
        "method": method_name,
        "selected_controls": ";".join(evaluation.selected_controls),
        "mean_residual_risk": evaluation.mean_residual_risk,
        "p90_residual_risk": evaluation.p90_residual_risk,
        "capex": evaluation.capex,
        "annual_control_opex": evaluation.annual_control_opex,
        "annual_ai_opex": evaluation.annual_ai_opex,
        "annual_opex": evaluation.annual_opex,
        "tco_3y": evaluation.tco_3y,
        "detection_rate": evaluation.detection_rate,
        "false_positive_rate": evaluation.false_positive_rate,
        "hf_reduction": evaluation.hf_reduction,
    }


def compute_hypervolume(frontier: pd.DataFrame, reference_point: tuple[float, float]) -> float:
    if frontier.empty:
        return 0.0
    points = frontier[["mean_residual_risk", "tco_3y"]].sort_values("mean_residual_risk").to_numpy(dtype=float)
    hv = 0.0
    prev_cost = reference_point[1]
    for residual, cost in points:
        width = max(reference_point[0] - residual, 0.0)
        height = max(prev_cost - cost, 0.0)
        hv += width * height
        prev_cost = min(prev_cost, cost)
    return float(hv)


def _normalize_recommendation_weights(weights: dict[str, float] | None = None) -> dict[str, float]:
    merged = DEFAULT_RECOMMENDATION_WEIGHTS.copy()
    if weights is not None:
        merged.update(weights)
    total = float(sum(max(value, 0.0) for value in merged.values()))
    if total <= 0.0:
        raise ValueError("Recommendation weights must contain positive mass.")
    return {key: max(value, 0.0) / total for key, value in merged.items()}


def choose_recommended_portfolio(frontier: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    scored = frontier.copy()
    recommendation_weights = _normalize_recommendation_weights(weights)
    for column in ["mean_residual_risk", "tco_3y", "false_positive_rate"]:
        denom = max(scored[column].max() - scored[column].min(), 1e-9)
        scored[f"{column}_norm"] = (scored[column] - scored[column].min()) / denom
    scored["detection_rate_norm"] = 1.0 - (
        (scored["detection_rate"] - scored["detection_rate"].min())
        / max(scored["detection_rate"].max() - scored["detection_rate"].min(), 1e-9)
    )
    scored["composite"] = (
        recommendation_weights["mean_residual_risk"] * scored["mean_residual_risk_norm"]
        + recommendation_weights["tco_3y"] * scored["tco_3y_norm"]
        + recommendation_weights["false_positive_rate"] * scored["false_positive_rate_norm"]
        + recommendation_weights["detection_rate"] * scored["detection_rate_norm"]
    )
    return scored.sort_values("composite").iloc[0]


def portfolio_selection_weight_sensitivity(
    frontier: pd.DataFrame,
    deltas: tuple[float, ...] = (-0.20, 0.20),
) -> pd.DataFrame:
    metric_labels = {
        "mean_residual_risk": "Mean residual risk weight",
        "tco_3y": "TCO weight",
        "false_positive_rate": "FPR weight",
        "detection_rate": "DR weight",
    }
    default_weights = _normalize_recommendation_weights()
    default_choice = choose_recommended_portfolio(frontier, default_weights)
    default_controls = str(default_choice["selected_controls"])
    rows: list[dict[str, object]] = [
        {
            "parameter": "Default artifact weights",
            "delta": 0.0,
            "weight_mean_residual_risk": float(default_weights["mean_residual_risk"]),
            "weight_tco_3y": float(default_weights["tco_3y"]),
            "weight_false_positive_rate": float(default_weights["false_positive_rate"]),
            "weight_detection_rate": float(default_weights["detection_rate"]),
            "selected_controls": default_controls,
            "mean_residual_risk": float(default_choice["mean_residual_risk"]),
            "p90_residual_risk": float(default_choice["p90_residual_risk"]),
            "tco_3y": float(default_choice["tco_3y"]),
            "detection_rate": float(default_choice["detection_rate"]),
            "false_positive_rate": float(default_choice["false_positive_rate"]),
            "matches_default_selection": True,
        }
    ]
    for metric, label in metric_labels.items():
        for delta in deltas:
            perturbed = default_weights.copy()
            perturbed[metric] *= 1.0 + delta
            normalized = _normalize_recommendation_weights(perturbed)
            selected = choose_recommended_portfolio(frontier, normalized)
            selected_controls = str(selected["selected_controls"])
            rows.append(
                {
                    "parameter": label,
                    "delta": float(delta),
                    "weight_mean_residual_risk": float(normalized["mean_residual_risk"]),
                    "weight_tco_3y": float(normalized["tco_3y"]),
                    "weight_false_positive_rate": float(normalized["false_positive_rate"]),
                    "weight_detection_rate": float(normalized["detection_rate"]),
                    "selected_controls": selected_controls,
                    "mean_residual_risk": float(selected["mean_residual_risk"]),
                    "p90_residual_risk": float(selected["p90_residual_risk"]),
                    "tco_3y": float(selected["tco_3y"]),
                    "detection_rate": float(selected["detection_rate"]),
                    "false_positive_rate": float(selected["false_positive_rate"]),
                    "matches_default_selection": selected_controls == default_controls,
                }
            )
    return pd.DataFrame(rows)


def _finalize_frontier(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=PORTFOLIO_RESULT_COLUMNS)
    frontier = pd.DataFrame(rows)
    frontier = frontier.drop_duplicates(subset=["selected_controls"]).sort_values(["mean_residual_risk", "tco_3y"]).reset_index(drop=True)
    costs = frontier["tco_3y"].to_numpy(dtype=float)
    keep = np.zeros(len(frontier), dtype=bool)
    best_cost_so_far = float("inf")
    for index, cost in enumerate(costs):
        if cost < best_cost_so_far - 1e-9:
            keep[index] = True
            best_cost_so_far = cost
    return frontier.loc[keep].reset_index(drop=True)


class PortfolioProblem(ElementwiseProblem):
    def __init__(
        self,
        control_frame: pd.DataFrame,
        base_risk: np.ndarray,
        base_detection_rate: float,
        base_fpr: float,
        budget: float,
    ) -> None:
        super().__init__(n_var=len(control_frame), n_obj=4, n_ieq_constr=1, xl=0, xu=1, type_var=bool)
        self.control_frame = control_frame.reset_index(drop=True)
        self.base_risk = base_risk
        self.base_detection_rate = base_detection_rate
        self.base_fpr = base_fpr
        self.budget = budget

    def _evaluate(self, x, out, *args, **kwargs):
        selection = np.asarray(x, dtype=bool)
        evaluation = evaluate_portfolio(self.control_frame, selection, self.base_risk, self.base_detection_rate, self.base_fpr)
        out["F"] = [
            evaluation.mean_residual_risk,
            evaluation.tco_3y,
            evaluation.false_positive_rate,
            -evaluation.detection_rate,
        ]
        out["G"] = [evaluation.capex - self.budget]


def run_nsga2(
    control_frame: pd.DataFrame,
    base_risk: np.ndarray,
    base_detection_rate: float,
    base_fpr: float,
    budget: float,
    population_size: int,
    generations: int,
    seed: int,
) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    problem = PortfolioProblem(control_frame, base_risk, base_detection_rate, base_fpr, budget)
    algorithm = NSGA2(
        pop_size=population_size,
        sampling=BinaryRandomSampling(),
        crossover=TwoPointCrossover(prob=0.9),
        mutation=BitflipMutation(prob=0.1),
        eliminate_duplicates=True,
    )
    result = minimize(problem, algorithm, ("n_gen", generations), seed=seed, verbose=False)
    rows: list[dict[str, object]] = []
    for vector in np.asarray(result.X):
        selection = np.asarray(vector, dtype=bool)
        evaluation = evaluate_portfolio(control_frame, selection, base_risk, base_detection_rate, base_fpr)
        if evaluation.capex <= budget + 1e-6:
            rows.append(
                {
                    "method": "NSGA-II",
                    "selected_controls": ";".join(evaluation.selected_controls),
                    "mean_residual_risk": evaluation.mean_residual_risk,
                    "p90_residual_risk": evaluation.p90_residual_risk,
                    "capex": evaluation.capex,
                    "annual_control_opex": evaluation.annual_control_opex,
                    "annual_ai_opex": evaluation.annual_ai_opex,
                    "annual_opex": evaluation.annual_opex,
                    "tco_3y": evaluation.tco_3y,
                    "detection_rate": evaluation.detection_rate,
                    "false_positive_rate": evaluation.false_positive_rate,
                    "hf_reduction": evaluation.hf_reduction,
                }
            )
    frontier = _finalize_frontier(rows)
    return frontier, time.perf_counter() - start


def run_greedy(
    control_frame: pd.DataFrame,
    base_risk: np.ndarray,
    base_detection_rate: float,
    base_fpr: float,
    budget: float,
) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    selected = np.zeros(len(control_frame), dtype=bool)
    running_capex = 0.0
    rows: list[dict[str, object]] = []
    while True:
        current_eval = evaluate_portfolio(control_frame, selected, base_risk, base_detection_rate, base_fpr)
        best_gain = 0.0
        best_index = None
        for index, row in control_frame.iterrows():
            if selected[index]:
                continue
            if running_capex + float(row["capex"]) > budget:
                continue
            candidate = selected.copy()
            candidate[index] = True
            eval_candidate = evaluate_portfolio(control_frame, candidate, base_risk, base_detection_rate, base_fpr)
            incremental_tco = float(row["capex"] + 3.0 * (row["opex"] + row["ai_opex"]))
            gain = (current_eval.mean_residual_risk - eval_candidate.mean_residual_risk) / max(incremental_tco, 1.0)
            if gain > best_gain:
                best_gain = gain
                best_index = index
        if best_index is None:
            break
        selected[best_index] = True
        running_capex += float(control_frame.iloc[best_index]["capex"])
        evaluation = evaluate_portfolio(control_frame, selected, base_risk, base_detection_rate, base_fpr)
        rows.append(_evaluation_to_row("Greedy", evaluation))
    if not rows:
        rows.append(_evaluation_to_row("Greedy", evaluate_portfolio(control_frame, selected, base_risk, base_detection_rate, base_fpr)))
    return _finalize_frontier(rows), time.perf_counter() - start


def run_exact_ilp(
    control_frame: pd.DataFrame,
    base_risk: np.ndarray,
    base_detection_rate: float,
    base_fpr: float,
    budget: float,
    max_controls_for_exact: int,
    min_detection_rate: float | None = None,
    max_false_positive_rate: float | None = None,
) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    if len(control_frame) > max_controls_for_exact:
        control_frame = control_frame.iloc[:max_controls_for_exact].copy()
    base_mean_risk = float(np.mean(base_risk))
    capex = control_frame["capex"].to_numpy(dtype=float)
    opex = (control_frame["opex"] + control_frame["ai_opex"]).to_numpy(dtype=float)
    log_effectiveness = np.log(np.clip(1.0 - control_frame["effectiveness"].to_numpy(dtype=float), 1e-6, 1.0))
    hf_delta = control_frame["hf_delta"].to_numpy(dtype=float)
    detect_gain = control_frame["detect_gain"].to_numpy(dtype=float)
    fpr_delta = control_frame["fpr_delta"].to_numpy(dtype=float)
    tau_grid = np.linspace(base_mean_risk * 0.22, base_mean_risk * 0.90, 16)
    solutions: list[dict[str, object]] = []

    for tau in tau_grid:
        problem = pulp.LpProblem("ExactPortfolio", pulp.LpMinimize)
        x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(control_frame))]
        problem += pulp.lpSum((capex[i] + 3.0 * opex[i]) * x[i] for i in range(len(control_frame)))
        problem += pulp.lpSum(capex[i] * x[i] for i in range(len(control_frame))) <= budget
        problem += math.log(base_mean_risk) + pulp.lpSum(log_effectiveness[i] * x[i] for i in range(len(control_frame))) <= math.log(tau)
        if min_detection_rate is not None:
            problem += base_detection_rate + pulp.lpSum(detect_gain[i] * x[i] for i in range(len(control_frame))) >= min_detection_rate
        if max_false_positive_rate is not None:
            problem += base_fpr + pulp.lpSum(fpr_delta[i] * x[i] for i in range(len(control_frame))) <= max_false_positive_rate
        status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
        if status != pulp.LpStatusOptimal:
            continue
        selection = np.asarray([bool(variable.value()) for variable in x], dtype=bool)
        evaluation = evaluate_portfolio(control_frame, selection, base_risk, base_detection_rate, base_fpr)
        solutions.append(_evaluation_to_row("Exact-ILP", evaluation))
    frontier = _finalize_frontier(solutions)
    return frontier, time.perf_counter() - start


def summarize_optimization_results(nsga2_frontier: pd.DataFrame, greedy_frontier: pd.DataFrame, exact_frontier: pd.DataFrame, base_risk: np.ndarray, budget: float, runtimes: dict[str, float]) -> pd.DataFrame:
    cost_candidates = [
        float(frontier["tco_3y"].max())
        for frontier in (nsga2_frontier, greedy_frontier, exact_frontier)
        if not frontier.empty
    ]
    reference_cost = max(cost_candidates, default=budget) * 1.05
    reference_point = (float(np.mean(base_risk)), reference_cost)
    rows: list[dict[str, object]] = []
    for method_name, frontier in [
        ("NSGA-II", nsga2_frontier),
        ("Greedy", greedy_frontier),
        ("Exact-ILP", exact_frontier),
    ]:
        if frontier.empty:
            continue
        best = choose_recommended_portfolio(frontier)
        rows.append(
            {
                "method": method_name,
                "best_mean_residual": float(best["mean_residual_risk"]),
                "best_p90_residual": float(best["p90_residual_risk"]),
                "capex": float(best["capex"]),
                "annual_control_opex": float(best["annual_control_opex"]),
                "annual_ai_opex": float(best["annual_ai_opex"]),
                "annual_opex": float(best["annual_opex"]),
                "tco_3y": float(best["tco_3y"]),
                "detection_rate": float(best["detection_rate"]),
                "false_positive_rate": float(best["false_positive_rate"]),
                "hypervolume": compute_hypervolume(frontier, reference_point),
                "pareto_size": int(len(frontier)),
                "runtime_s": float(runtimes[method_name]),
                "selected_controls": best["selected_controls"],
            }
        )
    return pd.DataFrame(rows).sort_values("best_mean_residual").reset_index(drop=True)


def compute_tco_from_components(capex: float, annual_opex: float) -> float:
    return compute_three_year_tco(capex=capex, annual_opex=annual_opex, annual_hidden=0.0)


def tco_sensitivity(
    baseline_portfolio: pd.Series,
    nsga2_portfolio: pd.Series,
) -> pd.DataFrame:
    perturb_columns = ["capex", "annual_control_opex", "annual_ai_opex"]
    rows: list[dict[str, object]] = []
    parameter_to_label = {
        "capex": "CapEx",
        "annual_control_opex": "Control OpEx",
        "annual_ai_opex": "AI OpEx",
    }
    for symbol in perturb_columns + ["ALL"]:
        for delta in (-0.20, 0.20):
            baseline_capex = float(baseline_portfolio["capex"])
            baseline_control_opex = float(baseline_portfolio["annual_control_opex"])
            baseline_ai_opex = float(baseline_portfolio["annual_ai_opex"])
            nsga_capex = float(nsga2_portfolio["capex"])
            nsga_control_opex = float(nsga2_portfolio["annual_control_opex"])
            nsga_ai_opex = float(nsga2_portfolio["annual_ai_opex"])
            if symbol == "ALL":
                baseline_capex *= 1.0 + delta
                baseline_control_opex *= 1.0 + delta
                baseline_ai_opex *= 1.0 + delta
                nsga_capex *= 1.0 + delta
                nsga_control_opex *= 1.0 + delta
                nsga_ai_opex *= 1.0 + delta
            elif symbol == "capex":
                baseline_capex *= 1.0 + delta
                nsga_capex *= 1.0 + delta
            elif symbol == "annual_control_opex":
                baseline_control_opex *= 1.0 + delta
                nsga_control_opex *= 1.0 + delta
            elif symbol == "annual_ai_opex":
                baseline_ai_opex *= 1.0 + delta
                nsga_ai_opex *= 1.0 + delta
            baseline_tco = compute_tco_from_components(baseline_capex, baseline_control_opex + baseline_ai_opex)
            nsga_tco = compute_tco_from_components(nsga_capex, nsga_control_opex + nsga_ai_opex)
            improvement = ((baseline_tco - nsga_tco) / baseline_tco) * 100.0
            rows.append(
                {
                    "parameter": parameter_to_label.get(symbol, "All parameters (joint)"),
                    "delta": delta,
                    "tco_baseline": baseline_tco,
                    "tco_nsga2": nsga_tco,
                    "improvement_pct": improvement,
                }
            )
    return pd.DataFrame(rows)
