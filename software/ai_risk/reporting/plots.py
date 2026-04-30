from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import precision_recall_curve, roc_curve

from ai_risk.metrics import reliability_curve_points
from ai_risk.utils.io import ensure_dir

sns.set_theme(style="whitegrid")


def _save(fig: plt.Figure, output_dir: str | Path, name: str, dpi: int = 180) -> Path:
    output_dir = ensure_dir(output_dir)
    path = output_dir / name
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_roc_curves(curves: dict[str, tuple], output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for label, (y_true, scores) in curves.items():
        fpr, tpr, _ = roc_curve(y_true, scores)
        ax.plot(fpr, tpr, label=label, linewidth=2)
    ax.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1)
    ax.set_title("ROC Curves")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.legend(frameon=True)
    return _save(fig, output_dir, "roc_curve.png", dpi=dpi)


def plot_pr_curves(curves: dict[str, tuple], output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for label, (y_true, scores) in curves.items():
        precision, recall, _ = precision_recall_curve(y_true, scores)
        ax.plot(recall, precision, label=label, linewidth=2)
    ax.set_title("Precision-Recall Curves")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.legend(frameon=True)
    return _save(fig, output_dir, "pr_curve.png", dpi=dpi)


def plot_reliability(y_true, scores, output_dir: str | Path, dpi: int = 180) -> Path:
    frame = reliability_curve_points(y_true, scores)
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    ax.plot(frame["predicted"], frame["observed"], marker="o", linewidth=2, label="Artifact-default scorer")
    ax.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1, label="Perfect calibration")
    ax.set_title("Reliability Curve")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.legend(frameon=True)
    return _save(fig, output_dir, "reliability_curve.png", dpi=dpi)


def plot_fixed_fpr(frame: pd.DataFrame, output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    ax.plot(frame["target_fpr"] * 100, frame["detection_rate"] * 100, marker="o", linewidth=2)
    ax.set_title("Fixed-FPR Operating Points")
    ax.set_xlabel("Target FPR (%)")
    ax.set_ylabel("Detection Rate (%)")
    return _save(fig, output_dir, "fixed_fpr_operating_points.png", dpi=dpi)


def plot_ids_bars(frame: pd.DataFrame, output_dir: str | Path, dpi: int = 180) -> Path:
    melted = frame.melt(id_vars=["Model"], value_vars=["F1", "AUROC", "FPR"], var_name="Metric", value_name="Value")
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    sns.barplot(data=melted, x="Model", y="Value", hue="Metric", ax=ax)
    ax.set_title("IDS Baseline Comparison")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=25)
    return _save(fig, output_dir, "ids_baselines_bar.png", dpi=dpi)


def plot_hf_ablation(frame: pd.DataFrame, output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    ax.plot(frame["w_H"], frame["ResidualRisk_mean"], marker="o", linewidth=2, label="Mean residual risk")
    ax.plot(frame["w_H"], frame["ResidualRisk_p90"], marker="s", linewidth=2, label="P90 residual risk")
    ax.set_title("Human-Factor Weight Ablation")
    ax.set_xlabel("w_H")
    ax.set_ylabel("Residual risk")
    ax.legend(frameon=True)
    return _save(fig, output_dir, "hf_ablation.png", dpi=dpi)


def plot_pareto_front(nsga2: pd.DataFrame, greedy: pd.DataFrame, exact: pd.DataFrame, output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    if not nsga2.empty:
        ax.scatter(nsga2["mean_residual_risk"], nsga2["tco_3y"], label="NSGA-II", s=44)
    if not greedy.empty:
        ax.scatter(greedy["mean_residual_risk"], greedy["tco_3y"], label="Greedy", s=80, marker="X")
    if not exact.empty:
        ax.scatter(exact["mean_residual_risk"], exact["tco_3y"], label="Exact-ILP", s=52, marker="D")
    ax.set_title("Pareto Front: Residual Risk vs Cost")
    ax.set_xlabel("Mean residual risk")
    ax.set_ylabel("Three-year control TCO")
    ax.legend(frameon=True)
    return _save(fig, output_dir, "pareto_front.png", dpi=dpi)


def plot_tco_sensitivity(pivot: pd.DataFrame, output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    plot_frame = pivot.reset_index().melt(id_vars="parameter", value_vars=["minus_20_pct", "plus_20_pct"], var_name="Scenario", value_name="Improvement")
    sns.barplot(data=plot_frame, x="parameter", y="Improvement", hue="Scenario", ax=ax)
    ax.set_title("TCO Sensitivity (+/-20%)")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Improvement (%)")
    return _save(fig, output_dir, "tco_sensitivity.png", dpi=dpi)


def plot_residual_distribution(base_risk: pd.Series, nsga_residual: pd.Series, baseline_residual: pd.Series, output_dir: str | Path, dpi: int = 180) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    sns.kdeplot(base_risk, label="Base risk", ax=ax, linewidth=2)
    sns.kdeplot(nsga_residual, label="NSGA-II residual", ax=ax, linewidth=2)
    sns.kdeplot(baseline_residual, label="Strongest baseline residual", ax=ax, linewidth=2)
    ax.set_title("Residual Risk Distribution")
    ax.set_xlabel("Risk")
    ax.legend(frameon=True)
    return _save(fig, output_dir, "residual_risk_distribution.png", dpi=dpi)
