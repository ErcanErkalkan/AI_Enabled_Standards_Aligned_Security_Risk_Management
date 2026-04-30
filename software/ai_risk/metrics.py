from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    auc,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


@dataclass
class ThresholdedMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    fpr: float
    auroc: float
    pr_auc: float
    brier: float
    threshold: float
    tn: int
    fp: int
    fn: int
    tp: int
    specificity: float
    balanced_accuracy: float
    mcc: float
    benign_recall: float
    false_alarms_per_1000_benign: float
    prevalence: float
    n_samples: int
    n_benign: int
    n_malicious: int


def select_threshold_by_f1(y_true: np.ndarray, scores: np.ndarray) -> float:
    candidates = np.unique(np.round(scores, 6))
    best_threshold = 0.5
    best_tuple = (-1.0, -1.0, -1.0)
    for threshold in candidates:
        predicted = (scores >= threshold).astype(int)
        f1 = f1_score(y_true, predicted, zero_division=0)
        recall = recall_score(y_true, predicted, zero_division=0)
        precision = precision_score(y_true, predicted, zero_division=0)
        ranking = (f1, recall, precision)
        if ranking > best_tuple:
            best_tuple = ranking
            best_threshold = float(threshold)
    return best_threshold


def compute_thresholded_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> ThresholdedMetrics:
    predicted = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    if len(np.unique(y_true)) < 2:
        auroc = 0.5
        pr_auc = float(np.mean(y_true))
    else:
        auroc = float(roc_auc_score(y_true, scores))
        pr_auc = float(average_precision_score(y_true, scores))
    
    n_benign = int(tn + fp)
    n_malicious = int(tp + fn)
    return ThresholdedMetrics(
        accuracy=float(accuracy_score(y_true, predicted)),
        precision=float(precision_score(y_true, predicted, zero_division=0)),
        recall=float(recall_score(y_true, predicted, zero_division=0)),
        f1=float(f1_score(y_true, predicted, zero_division=0)),
        fpr=float(fp / max(fp + tn, 1)),
        auroc=auroc,
        pr_auc=pr_auc,
        brier=float(brier_score_loss(y_true, np.clip(scores, 0.0, 1.0))),
        threshold=float(threshold),
        tn=int(tn),
        fp=int(fp),
        fn=int(fn),
        tp=int(tp),
        specificity=float(tn / max(tn + fp, 1)),
        balanced_accuracy=float(balanced_accuracy_score(y_true, predicted)),
        mcc=float(matthews_corrcoef(y_true, predicted)),
        benign_recall=float(tn / max(tn + fp, 1)),
        false_alarms_per_1000_benign=float(fp / max(n_benign, 1) * 1000),
        prevalence=float(n_malicious / max(n_benign + n_malicious, 1)),
        n_samples=int(len(y_true)),
        n_benign=n_benign,
        n_malicious=n_malicious,
    )


def reliability_curve_points(y_true: np.ndarray, scores: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    prob_true, prob_pred = calibration_curve(y_true, scores, n_bins=n_bins, strategy="quantile")
    return pd.DataFrame({"predicted": prob_pred, "observed": prob_true})


def fixed_fpr_operating_points(
    reference_y_true: np.ndarray,
    reference_scores: np.ndarray,
    *,
    evaluation_y_true: np.ndarray | None = None,
    evaluation_scores: np.ndarray | None = None,
    fpr_targets: list[float] | None = None,
) -> pd.DataFrame:
    fpr_targets = fpr_targets or [0.01, 0.02, 0.03, 0.04, 0.05]
    reference_y_true = np.asarray(reference_y_true, dtype=int)
    reference_scores = np.asarray(reference_scores, dtype=float)
    evaluation_y_true = reference_y_true if evaluation_y_true is None else np.asarray(evaluation_y_true, dtype=int)
    evaluation_scores = reference_scores if evaluation_scores is None else np.asarray(evaluation_scores, dtype=float)
    valid_reference = ~np.isnan(reference_scores)
    if not valid_reference.any():
        raise ValueError("Reference scores for fixed-FPR selection contain no finite values.")
    reference_fpr, reference_tpr, thresholds = roc_curve(reference_y_true[valid_reference], reference_scores[valid_reference])
    rows = []
    for target in fpr_targets:
        feasible = np.where(reference_fpr <= target)[0]
        if len(feasible):
            index = int(feasible[np.argmax(reference_tpr[feasible])])
        else:
            index = int(np.argmin(reference_fpr))
        threshold = float(thresholds[index])
        metrics = compute_thresholded_metrics(evaluation_y_true, evaluation_scores, threshold)
        row = {
            "target_fpr": target,
            "threshold": metrics.threshold,
            "reference_fpr": float(reference_fpr[index]),
            "reference_detection_rate": float(reference_tpr[index]),
            "realized_fpr": metrics.fpr,
            "detection_rate": metrics.recall,
            "tn": metrics.tn,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "tp": metrics.tp,
            "specificity": metrics.specificity,
            "balanced_accuracy": metrics.balanced_accuracy,
            "mcc": metrics.mcc,
            "benign_recall": metrics.benign_recall,
            "false_alarms_per_1000_benign": metrics.false_alarms_per_1000_benign,
            "prevalence": metrics.prevalence,
            "n_samples": metrics.n_samples,
            "n_benign": metrics.n_benign,
            "n_malicious": metrics.n_malicious,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def per_time_block_metric_series(meta: pd.DataFrame, y_true: np.ndarray, scores: np.ndarray, threshold: float, n_blocks: int = 10) -> pd.DataFrame:
    frame = meta.copy()
    frame["y_true"] = y_true
    frame["score"] = scores
    frame["pred"] = (scores >= threshold).astype(int)
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    repeats = int(np.ceil(len(ordered) / max(n_blocks, 1)))
    ordered["block"] = np.repeat(np.arange(n_blocks), repeats=repeats)[: len(ordered)]
    rows: list[dict[str, float | int]] = []
    for block, group in ordered.groupby("block"):
        tn, fp, fn, tp = confusion_matrix(group["y_true"], group["pred"], labels=[0, 1]).ravel()
        rows.append(
            {
                "block": int(block),
                "f1": float(f1_score(group["y_true"], group["pred"], zero_division=0)),
                "auroc": float(roc_auc_score(group["y_true"], group["score"])) if group["y_true"].nunique() > 1 else 0.5,
                "fpr": float(fp / max(fp + tn, 1)),
            }
        )
    return pd.DataFrame(rows)
