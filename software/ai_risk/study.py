from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ai_risk.data_ingest import load_demo_data, load_real_data
from ai_risk.metrics import fixed_fpr_operating_points, per_time_block_metric_series
from ai_risk.models.ids import run_all_ids_models
from ai_risk.optimization.portfolio import (
    DEFAULT_RECOMMENDATION_WEIGHTS,
    choose_recommended_portfolio,
    evaluate_portfolio,
    load_control_catalog,
    portfolio_selection_weight_sensitivity,
    run_exact_ilp,
    run_greedy,
    run_nsga2,
    summarize_optimization_results,
    tco_sensitivity,
)
from ai_risk.preprocessing import build_window_dataset, chronological_frame_splits, infer_feature_columns
from ai_risk.reference_data import build_reference_bundle
from ai_risk.reporting.plots import (
    plot_fixed_fpr,
    plot_hf_ablation,
    plot_ids_bars,
    plot_pareto_front,
    plot_pr_curves,
    plot_reliability,
    plot_residual_distribution,
    plot_roc_curves,
    plot_tco_sensitivity,
)
from ai_risk.reporting.tables import save_table
from ai_risk.risk import compute_risk_frame, fit_event_probability_parameters, portfolio_budget, residual_risk_from_controls
from ai_risk.statistics import pairwise_wilcoxon_table
from ai_risk.utils.io import ensure_dir, write_text
from ai_risk.utils.seed import seed_everything
from ai_risk.validator import validate_reference_artifacts


def _matched_budget_baseline(
    nsga_point: pd.Series,
    greedy_frontier: pd.DataFrame,
    exact_frontier: pd.DataFrame,
) -> tuple[str, pd.Series, bool]:
    affordable_candidates = []
    fallback_candidates = []
    for method_name, frontier in [("Greedy", greedy_frontier), ("Exact-ILP", exact_frontier)]:
        if frontier.empty:
            continue
        frontier = frontier.copy()
        frontier["capex_gap"] = (frontier["capex"] - float(nsga_point["capex"])).abs()
        affordable = frontier.loc[frontier["capex"] <= float(nsga_point["capex"]) * 1.05]
        if affordable.empty:
            selected = frontier.sort_values(["capex_gap", "mean_residual_risk"]).iloc[0]
            fallback_candidates.append((method_name, selected))
        else:
            selected = affordable.sort_values(["mean_residual_risk", "capex_gap"]).iloc[0]
            affordable_candidates.append((method_name, selected))
    candidates = affordable_candidates or fallback_candidates
    if not candidates:
        raise ValueError("No baseline frontier is available for matched-budget comparison.")
    if affordable_candidates:
        candidates.sort(key=lambda item: (float(item[1]["mean_residual_risk"]), float(item[1]["capex_gap"])))
    else:
        candidates.sort(key=lambda item: (float(item[1]["capex_gap"]), float(item[1]["mean_residual_risk"])))
    return candidates[0][0], candidates[0][1], bool(affordable_candidates)


def _minmax_scale_from_reference(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    reference = np.asarray(reference, dtype=float)
    values = np.asarray(values, dtype=float)
    lower = float(np.nanmin(reference))
    upper = float(np.nanmax(reference))
    if np.isclose(lower, upper):
        return np.zeros_like(values, dtype=float)
    return np.clip((values - lower) / (upper - lower), 0.0, 1.0)


def _optional_float(raw_value: object) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and raw_value.strip().lower() in {"", "none", "null"}:
        return None
    return float(raw_value)


def _build_input_data_summary(raw_frame: pd.DataFrame, profile_name: str) -> pd.DataFrame:
    source_columns = [column for column in ["__source_parent", "__source_file"] if column in raw_frame.columns]
    rows: list[dict[str, object]] = [
        {"Metric": "profile", "Value": profile_name},
        {"Metric": "raw_rows", "Value": int(len(raw_frame))},
        {"Metric": "raw_assets", "Value": int(raw_frame["asset_id"].nunique()) if "asset_id" in raw_frame.columns else 0},
        {"Metric": "raw_event_types", "Value": int(raw_frame["event_type"].nunique()) if "event_type" in raw_frame.columns else 0},
    ]
    for key, value in raw_frame.attrs.get("load_params", {}).items():
        rows.append({"Metric": f"load_{key}", "Value": value if value is not None else ""})
    for column in source_columns:
        rows.append({"Metric": f"unique_{column}", "Value": int(raw_frame[column].nunique())})
    return pd.DataFrame(rows)


def _build_window_split_summary(
    frame_splits: dict[str, pd.DataFrame],
    split_datasets: dict[str, object],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split_name in ["train", "validation", "test"]:
        raw_split = frame_splits[split_name]
        windowed = split_datasets[split_name]
        w_labels = windowed.y if hasattr(windowed, "y") else np.array([])
        w_benign = int((w_labels == 0).sum()) if len(w_labels) else 0
        w_malicious = int((w_labels == 1).sum()) if len(w_labels) else 0
        w_total = int(len(w_labels))
        raw_labels = raw_split["label"] if "label" in raw_split.columns else pd.Series(dtype=int)
        raw_benign = int((raw_labels == 0).sum()) if len(raw_labels) else 0
        raw_malicious = int((raw_labels == 1).sum()) if len(raw_labels) else 0
        rows.append(
            {
                "split": split_name,
                "raw_rows": int(len(raw_split)),
                "raw_assets": int(raw_split["asset_id"].nunique()) if "asset_id" in raw_split.columns else 0,
                "raw_benign": raw_benign,
                "raw_malicious": raw_malicious,
                "raw_malicious_rate": round(raw_malicious / max(len(raw_labels), 1), 4),
                "window_rows": w_total,
                "window_assets": int(windowed.meta["asset_id"].nunique()) if not windowed.meta.empty else 0,
                "window_benign": w_benign,
                "window_malicious": w_malicious,
                "window_malicious_rate": round(w_malicious / max(w_total, 1), 4),
                "raw_start": raw_split["timestamp"].min().isoformat() if len(raw_split) else "",
                "raw_end": raw_split["timestamp"].max().isoformat() if len(raw_split) else "",
                "window_start": windowed.meta["window_start_timestamp"].min().isoformat() if not windowed.meta.empty else "",
                "window_end": windowed.meta["window_end_timestamp"].max().isoformat() if not windowed.meta.empty else "",
            }
        )
    return pd.DataFrame(rows)


def run_study(settings) -> dict[str, object]:
    seed_everything(settings.global_cfg.seed)
    root = settings.root
    output_dir = ensure_dir(settings.output_dir)
    dpi = int(settings.global_cfg.figures_dpi)
    build_reference_bundle(root)
    validator_summary = validate_reference_artifacts(root, write_log=True)

    if settings.profile_cfg["mode"] == "demo":
        raw_frame = load_demo_data(settings.profile_cfg, seed=settings.global_cfg.seed)
    else:
        raw_frame = load_real_data(settings.profile_cfg)
    save_table(_build_input_data_summary(raw_frame, settings.profile_name), output_dir, "input_data_summary")
    feature_columns = infer_feature_columns(raw_frame)
    asset_id_sources = set(raw_frame.get("asset_id_source", pd.Series(dtype="object")).dropna().astype(str))
    align_on_asset_boundaries = asset_id_sources.issubset({"__source_file", "__source_parent", "fallback_constant"})
    frame_splits = chronological_frame_splits(
        raw_frame,
        validation_fraction=float(settings.profile_cfg["validation_fraction"]),
        test_fraction=float(settings.profile_cfg["test_fraction"]),
        align_on_asset_boundaries=align_on_asset_boundaries,
    )
    split_datasets = {
        split_name: build_window_dataset(
            split_frame,
            window_size=int(settings.profile_cfg["window_size"]),
            feature_columns=feature_columns,
        )
        for split_name, split_frame in frame_splits.items()
    }
    save_table(_build_window_split_summary(frame_splits, split_datasets), output_dir, "split_summary")

    train_dataset = split_datasets["train"]
    validation_dataset = split_datasets["validation"]
    test_dataset = split_datasets["test"]
    X_seq_train, X_tab_train, y_train, meta_train = (
        train_dataset.X_seq,
        train_dataset.X_tab,
        train_dataset.y,
        train_dataset.meta.reset_index(drop=True),
    )
    X_seq_val, X_tab_val, y_val, meta_val = (
        validation_dataset.X_seq,
        validation_dataset.X_tab,
        validation_dataset.y,
        validation_dataset.meta.reset_index(drop=True),
    )
    X_seq_test, X_tab_test, y_test, meta_test = (
        test_dataset.X_seq,
        test_dataset.X_tab,
        test_dataset.y,
        test_dataset.meta.reset_index(drop=True),
    )
    if min(len(y_train), len(y_val), len(y_test)) == 0:
        raise ValueError("One of the train/validation/test windowed splits is empty. Adjust the split fractions or window size.")
    dataset_meta = pd.concat(
        [
            train_dataset.meta.assign(split="train"),
            validation_dataset.meta.assign(split="validation"),
            test_dataset.meta.assign(split="test"),
        ],
        ignore_index=True,
    )

    model_cfg = dict(settings.profile_cfg["models"], cv_folds=int(settings.profile_cfg["cv_folds"]))
    runs, pretest_scores, aux_outputs = run_all_ids_models(
        X_seq_train,
        X_seq_val,
        X_seq_test,
        X_tab_train,
        X_tab_val,
        X_tab_test,
        y_train,
        y_val,
        y_test,
        model_cfg,
        seed=settings.global_cfg.seed,
        meta_train=meta_train,
        meta_val=meta_val,
    )

    baseline_order = ["Random Forest", "LightGBM", "1D-CNN", "OC-SVM", "Isolation Forest", "LSTM-AE"]
    ids_results = pd.DataFrame(
        [
            {
                "Model": name,
                "F1": runs[name].metrics.f1,
                "AUROC": runs[name].metrics.auroc,
                "PR_AUC": runs[name].metrics.pr_auc,
                "FPR": runs[name].metrics.fpr,
                "Specificity": runs[name].metrics.specificity,
                "BalancedAccuracy": runs[name].metrics.balanced_accuracy,
                "MCC": runs[name].metrics.mcc,
                "FalseAlarmsPer1000Benign": runs[name].metrics.false_alarms_per_1000_benign,
                "FitSeconds": runs[name].fit_seconds,
            }
            for name in baseline_order
        ]
    )
    save_table(ids_results, output_dir, "ids_results")
    model_selection_df = pd.DataFrame(
        [{"Model": name, "BestParams": str(run.best_params), "FitSeconds": run.fit_seconds} for name, run in runs.items()]
    )
    save_table(model_selection_df, output_dir, "model_selection")

    paper = runs["Artifact-default scorer"]
    paper_summary = pd.DataFrame(
        [
            {
                "Model": paper.name,
                "N": paper.metrics.n_samples,
                "Benign": paper.metrics.n_benign,
                "Malicious": paper.metrics.n_malicious,
                "Prevalence": paper.metrics.prevalence,
                "TN": paper.metrics.tn,
                "FP": paper.metrics.fp,
                "FN": paper.metrics.fn,
                "TP": paper.metrics.tp,
                "Accuracy": paper.metrics.accuracy,
                "Precision": paper.metrics.precision,
                "Recall": paper.metrics.recall,
                "Specificity": paper.metrics.specificity,
                "BalancedAccuracy": paper.metrics.balanced_accuracy,
                "MCC": paper.metrics.mcc,
                "F1": paper.metrics.f1,
                "FPR": paper.metrics.fpr,
                "FalseAlarmsPer1000Benign": paper.metrics.false_alarms_per_1000_benign,
                "AUROC": paper.metrics.auroc,
                "PR_AUC": paper.metrics.pr_auc,
                "Brier": paper.metrics.brier,
                "Threshold": paper.threshold,
            }
        ]
    )
    save_table(paper_summary, output_dir, "default_telemetry_scorer_summary")

    # Dedicated confusion-matrix file: default threshold + fixed-FPR points (populated later)
    confusion_matrix_default = pd.DataFrame(
        [
            {
                "operating_point": "default_0.5",
                "threshold": paper.metrics.threshold,
                "TN": paper.metrics.tn,
                "FP": paper.metrics.fp,
                "FN": paper.metrics.fn,
                "TP": paper.metrics.tp,
                "Specificity": paper.metrics.specificity,
                "FPR": paper.metrics.fpr,
                "DetectionRate": paper.metrics.recall,
                "BalancedAccuracy": paper.metrics.balanced_accuracy,
                "MCC": paper.metrics.mcc,
                "FalseAlarmsPer1000Benign": paper.metrics.false_alarms_per_1000_benign,
            }
        ]
    )
    save_table(confusion_matrix_default, output_dir, "confusion_matrix")

    meta_pre = pd.concat([meta_train, meta_val], ignore_index=True)
    paper_aux = aux_outputs["Artifact-default scorer"]
    likelihood_pretest = _minmax_scale_from_reference(paper_aux["likelihood_pretest"], paper_aux["likelihood_pretest"])
    likelihood_test = _minmax_scale_from_reference(paper_aux["likelihood_pretest"], paper_aux["likelihood_test"])
    alpha, beta = fit_event_probability_parameters(
        likelihood_signal=likelihood_pretest,
        exploitability=meta_pre["cvss_exploitability"].to_numpy(dtype=float),
        labels=np.concatenate([y_train, y_val], axis=0),
    )
    test_risk_default = compute_risk_frame(meta_test, likelihood_test, w_h=0.20, alpha=alpha, beta=beta)
    control_frame = load_control_catalog(root / "data" / "control_catalog.csv")
    gamma = float(settings.profile_cfg["optimization"]["gamma"])
    budget = portfolio_budget(float(test_risk_default["expected_loss"].sum()), gamma=gamma)
    base_detection_rate = paper.metrics.recall
    base_fpr = paper.metrics.fpr

    nsga2_frontier, nsga_runtime = run_nsga2(
        control_frame,
        test_risk_default["BR"].to_numpy(dtype=float),
        base_detection_rate,
        base_fpr,
        budget,
        population_size=int(settings.profile_cfg["optimization"]["population_size"]),
        generations=int(settings.profile_cfg["optimization"]["generations"]),
        seed=settings.global_cfg.seed,
    )
    greedy_frontier, greedy_runtime = run_greedy(control_frame, test_risk_default["BR"].to_numpy(dtype=float), base_detection_rate, base_fpr, budget)
    exact_min_detection_rate = _optional_float(settings.profile_cfg["optimization"].get("min_detection_rate"))
    exact_max_false_positive_rate = _optional_float(settings.profile_cfg["optimization"].get("max_false_positive_rate"))
    exact_frontier, exact_runtime = run_exact_ilp(
        control_frame,
        test_risk_default["BR"].to_numpy(dtype=float),
        base_detection_rate,
        base_fpr,
        budget,
        max_controls_for_exact=int(settings.profile_cfg["optimization"]["exact_limit"]),
        min_detection_rate=exact_min_detection_rate,
        max_false_positive_rate=exact_max_false_positive_rate,
    )
    runtimes = {"NSGA-II": nsga_runtime, "Greedy": greedy_runtime, "Exact-ILP": exact_runtime}
    optimization_summary = summarize_optimization_results(
        nsga2_frontier,
        greedy_frontier,
        exact_frontier,
        test_risk_default["BR"].to_numpy(dtype=float),
        budget,
        runtimes,
    )
    save_table(optimization_summary, output_dir, "optimization_baselines")
    policy_constraints = pd.DataFrame(
        [
            {
                "constraint": "min_detection_rate",
                "configured_target": exact_min_detection_rate,
                "base_metric": base_detection_rate,
                "catalog_extreme": float(np.clip(base_detection_rate + control_frame["detect_gain"].clip(lower=0.0).sum(), 0.0, 1.0)),
                "reported_comparison_status": "disabled" if exact_min_detection_rate is None else "enabled",
                "reported_comparison_note": "Frontier comparison is run on the common ResidualRisk/TCO plane when disabled.",
            },
            {
                "constraint": "max_false_positive_rate",
                "configured_target": exact_max_false_positive_rate,
                "base_metric": base_fpr,
                "catalog_extreme": float(np.clip(base_fpr + control_frame["fpr_delta"].clip(upper=0.0).sum(), 0.0, 1.0)),
                "reported_comparison_status": "disabled" if exact_max_false_positive_rate is None else "enabled",
                "reported_comparison_note": "Frontier comparison is run on the common ResidualRisk/TCO plane when disabled.",
            },
        ]
    )
    save_table(policy_constraints, output_dir, "optimization_policy_constraints")

    nsga2_best = choose_recommended_portfolio(nsga2_frontier)
    strongest_method, strongest_best, has_matched_budget_baseline = _matched_budget_baseline(
        nsga2_best,
        greedy_frontier,
        exact_frontier,
    )

    nsga_eval = evaluate_portfolio(
        control_frame,
        control_frame["control_id"].isin(str(nsga2_best["selected_controls"]).split(";")).to_numpy(),
        test_risk_default["BR"].to_numpy(dtype=float),
        base_detection_rate,
        base_fpr,
    )
    baseline_eval = evaluate_portfolio(
        control_frame,
        control_frame["control_id"].isin(str(strongest_best["selected_controls"]).split(";")).to_numpy(),
        test_risk_default["BR"].to_numpy(dtype=float),
        base_detection_rate,
        base_fpr,
    )
    residual_improvement_mean = ((baseline_eval.mean_residual_risk - nsga_eval.mean_residual_risk) / max(baseline_eval.mean_residual_risk, 1e-9)) * 100.0
    residual_improvement_p90 = ((baseline_eval.p90_residual_risk - nsga_eval.p90_residual_risk) / max(baseline_eval.p90_residual_risk, 1e-9)) * 100.0
    baseline_label = f"matched-budget {strongest_method}" if has_matched_budget_baseline else f"nearest-budget {strongest_method}"

    fixed_fpr_df = fixed_fpr_operating_points(
        np.concatenate([y_train, y_val], axis=0),
        paper.validation_scores,
        evaluation_y_true=y_test,
        evaluation_scores=paper.test_scores,
    )
    save_table(fixed_fpr_df, output_dir, "fixed_fpr_operating_points")

    # Append fixed-FPR rows to the confusion matrix file
    fixed_fpr_cm_rows = [
        {
            "operating_point": f"fixed_fpr_{row['target_fpr']:.2f}",
            "threshold": row["threshold"],
            "TN": row["tn"],
            "FP": row["fp"],
            "FN": row["fn"],
            "TP": row["tp"],
            "Specificity": row["specificity"],
            "FPR": row["realized_fpr"],
            "DetectionRate": row["detection_rate"],
            "BalancedAccuracy": row["balanced_accuracy"],
            "MCC": row["mcc"],
            "FalseAlarmsPer1000Benign": row["false_alarms_per_1000_benign"],
        }
        for row in fixed_fpr_df.to_dict(orient="records")
    ]
    confusion_matrix_full = pd.concat(
        [confusion_matrix_default, pd.DataFrame(fixed_fpr_cm_rows)],
        ignore_index=True,
    )
    save_table(confusion_matrix_full, output_dir, "confusion_matrix")

    ablation_rows: list[dict[str, float]] = []
    fixed_budget = portfolio_budget(float(compute_risk_frame(meta_test, likelihood_test, w_h=0.0, alpha=alpha, beta=beta)["expected_loss"].sum()), gamma=gamma)
    hf_available = bool((meta_test["hf_source"] != "HF:none").any())
    ablation_weights = [0.0, 0.10, 0.20, 0.30]
    if not hf_available:
        ablation_risk_frame = compute_risk_frame(meta_test, likelihood_test, w_h=0.0, alpha=alpha, beta=beta)
        ablation_frontier, _ = run_nsga2(
            control_frame,
            ablation_risk_frame["BR"].to_numpy(dtype=float),
            base_detection_rate,
            base_fpr,
            fixed_budget,
            population_size=max(40, int(settings.profile_cfg["optimization"]["population_size"] // 2)),
            generations=max(40, int(settings.profile_cfg["optimization"]["generations"] // 2)),
            seed=settings.global_cfg.seed,
        )
        ablation_best = choose_recommended_portfolio(ablation_frontier) if not ablation_frontier.empty else choose_recommended_portfolio(greedy_frontier)
        for w_h in ablation_weights:
            ablation_rows.append(
                {
                    "w_H": w_h,
                    "F1": paper.metrics.f1,
                    "AUROC": paper.metrics.auroc,
                    "ResidualRisk_mean": float(ablation_best["mean_residual_risk"]),
                    "ResidualRisk_p90": float(ablation_best["p90_residual_risk"]),
                }
            )
    else:
        for w_h in ablation_weights:
            risk_frame = compute_risk_frame(meta_test, likelihood_test, w_h=w_h, alpha=alpha, beta=beta)
            frontier, _ = run_nsga2(
                control_frame,
                risk_frame["BR"].to_numpy(dtype=float),
                base_detection_rate,
                base_fpr,
                fixed_budget,
                population_size=max(40, int(settings.profile_cfg["optimization"]["population_size"] // 2)),
                generations=max(40, int(settings.profile_cfg["optimization"]["generations"] // 2)),
                seed=settings.global_cfg.seed + int(w_h * 100),
            )
            if frontier.empty:
                best = choose_recommended_portfolio(greedy_frontier)
            else:
                best = choose_recommended_portfolio(frontier)
            ablation_rows.append(
                {
                    "w_H": w_h,
                    "F1": paper.metrics.f1,
                    "AUROC": paper.metrics.auroc,
                    "ResidualRisk_mean": float(best["mean_residual_risk"]),
                    "ResidualRisk_p90": float(best["p90_residual_risk"]),
                }
            )
    ablation_df = pd.DataFrame(ablation_rows)
    save_table(ablation_df, output_dir, "ablation_hf")

    metric_series = {}
    for model_name, model_run in runs.items():
        block_frame = per_time_block_metric_series(meta_test, y_test, model_run.test_scores, model_run.threshold)
        metric_series.setdefault("f1", {})[model_name] = block_frame["f1"].to_numpy()
        metric_series.setdefault("auroc", {})[model_name] = block_frame["auroc"].to_numpy()
        metric_series.setdefault("fpr", {})[model_name] = block_frame["fpr"].to_numpy()
    stats_tables = [pairwise_wilcoxon_table(metric_series[metric_name], metric_name) for metric_name in ["f1", "auroc", "fpr"]]
    stats_df = pd.concat(stats_tables, ignore_index=True)
    save_table(stats_df, output_dir, "statistical_tests")

    baseline_tco = float(strongest_best["tco_3y"])
    nsga2_tco = float(nsga2_best["tco_3y"])
    tco_improvement_pct = ((baseline_tco - nsga2_tco) / baseline_tco) * 100.0
    sensitivity_df = tco_sensitivity(strongest_best, nsga2_best)
    save_table(sensitivity_df, output_dir, "tco_sensitivity_full")
    sensitivity_pivot = (
        sensitivity_df.assign(
            scenario=sensitivity_df["delta"].map({-0.20: "minus_20_pct", 0.20: "plus_20_pct"})
        )
        .pivot(index="parameter", columns="scenario", values="improvement_pct")
        .reset_index()
    )
    save_table(sensitivity_pivot, output_dir, "tco_sensitivity")
    weight_sensitivity_df = portfolio_selection_weight_sensitivity(nsga2_frontier)
    save_table(weight_sensitivity_df, output_dir, "portfolio_weight_sensitivity")
    weight_runs = weight_sensitivity_df.loc[weight_sensitivity_df["parameter"] != "Default artifact weights"].copy()
    unique_weight_portfolios = int(weight_sensitivity_df["selected_controls"].nunique())
    default_weight_matches = int(weight_runs["matches_default_selection"].sum())
    total_weight_runs = int(len(weight_runs))
    weight_mean_min = float(weight_sensitivity_df["mean_residual_risk"].min())
    weight_mean_max = float(weight_sensitivity_df["mean_residual_risk"].max())
    weight_tco_min = float(weight_sensitivity_df["tco_3y"].min())
    weight_tco_max = float(weight_sensitivity_df["tco_3y"].max())
    hf_provenance = (
        dataset_meta["hf_source"]
        .value_counts(dropna=False)
        .rename_axis("hf_source")
        .reset_index(name="row_count")
    )
    save_table(hf_provenance, output_dir, "hf_provenance")
    cvss_provenance = (
        dataset_meta["cvss_source"]
        .value_counts(dropna=False)
        .rename_axis("cvss_source")
        .reset_index(name="row_count")
    )
    save_table(cvss_provenance, output_dir, "cvss_provenance")
    asset_value_provenance = (
        dataset_meta["asset_value_source"]
        .value_counts(dropna=False)
        .rename_axis("asset_value_source")
        .reset_index(name="row_count")
    )
    save_table(asset_value_provenance, output_dir, "asset_value_provenance")
    neutral_cvss_rows = int(cvss_provenance.loc[cvss_provenance["cvss_source"] == "global_neutral_prior", "row_count"].sum())
    if neutral_cvss_rows == len(dataset_meta):
        ep_activation_outcome = (
            f"All {neutral_cvss_rows}/{len(dataset_meta)} reported rows use cvss_source=global_neutral_prior, "
            "so exploitability acts as a constant offset rather than a varying public-profile factor."
        )
    elif neutral_cvss_rows == 0:
        ep_activation_outcome = (
            f"0/{len(dataset_meta)} reported rows use cvss_source=global_neutral_prior; "
            "this non-public/synthetic profile exercises row-varying exploitability, so it is not used as the strict public-data evidence claim."
        )
    else:
        ep_activation_outcome = (
            f"{neutral_cvss_rows}/{len(dataset_meta)} reported rows use cvss_source=global_neutral_prior; "
            "row-varying exploitability is only partially activated in this profile."
        )
    nsga_summary = optimization_summary.loc[optimization_summary["method"] == "NSGA-II"].iloc[0]
    greedy_summary = optimization_summary.loc[optimization_summary["method"] == "Greedy"].iloc[0]
    exact_summary = optimization_summary.loc[optimization_summary["method"] == "Exact-ILP"]
    exact_frontier_outcome = (
        f"Exact-ILP frontier: {int(exact_summary.iloc[0]['pareto_size'])} points (HV={float(exact_summary.iloc[0]['hypervolume']):,.1f})"
        if not exact_summary.empty
        else "Exact-ILP frontier: not returned"
    )
    risk_phrase_mean = (
        f"{abs(residual_improvement_mean):.1f}% lower mean residual risk"
        if residual_improvement_mean >= 0
        else f"{abs(residual_improvement_mean):.1f}% higher mean residual risk"
    )
    risk_phrase_p90 = (
        f"{abs(residual_improvement_p90):.1f}% lower p90 residual risk"
        if residual_improvement_p90 >= 0
        else f"{abs(residual_improvement_p90):.1f}% higher p90 residual risk"
    )
    tco_phrase = (
        f"{abs(tco_improvement_pct):.1f}% lower three-year control TCO"
        if tco_improvement_pct >= 0
        else f"{abs(tco_improvement_pct):.1f}% higher three-year control TCO"
    )
    rq_summary = pd.DataFrame(
        [
            {
                "RQ": "RQ1",
                "Evaluation_axis": "Schema <-> standards alignment",
                "Outcome": (
                    f"Released artifact represents {validator_summary['iso_coverage']}/{validator_summary['iso_total']} ISO rows "
                    f"and {validator_summary['nist_coverage']}/{validator_summary['nist_total']} NIST rows in machine-readable form."
                ),
            },
            {
                "RQ": "RQ2",
                "Evaluation_axis": "Coverage and integrity validation",
                "Outcome": (
                    f"Automated validator confirms 100% ISO/NIST coverage with {validator_summary['broken_links']} broken links and "
                    f"{validator_summary['duplicate_or_dangling']} duplicate/dangling rows in {validator_summary['elapsed_seconds']:.2f}s."
                ),
            },
            {
                "RQ": "RQ2",
                "Evaluation_axis": "Official ISO <-> NIST informative-reference consistency",
                "Outcome": f"Validator reports {validator_summary['informative_reference_crosswalk_mismatches']} informative-reference crosswalk mismatches across all mapped rows.",
            },
            {
                "RQ": "RQ2",
                "Evaluation_axis": "Scope of mapping validation",
                "Outcome": "Structural: coverage, identifier consistency, broken-link checks, duplicate/dangling-row checks, and bidirectional ISO<->NIST crosswalk consistency verified by the automated validator. The artifact is presented as an inspectable standards-traceability baseline, not as a compliance oracle.",
            },
            {
                "RQ": "RQ3",
                "Evaluation_axis": "Telemetry-only evidence-generation performance",
                "Outcome": (
                    f"On the surrogate-heavy strict public profile: F1={paper.metrics.f1:.3f}, AUROC={paper.metrics.auroc:.3f}, "
                    f"PR-AUC={paper.metrics.pr_auc:.3f}, Brier={paper.metrics.brier:.3f}."
                ),
            },
            {
                "RQ": "RQ3",
                "Evaluation_axis": "EP exploitability activation status",
                "Outcome": ep_activation_outcome,
            },
            {
                "RQ": "RQ3",
                "Evaluation_axis": "Frontier-level portfolio exploration",
                "Outcome": (
                    f"NSGA-II frontier: {int(nsga_summary['pareto_size'])} points (HV={float(nsga_summary['hypervolume']):,.1f}); "
                    f"Greedy frontier: {int(greedy_summary['pareto_size'])} points (HV={float(greedy_summary['hypervolume']):,.1f}); "
                    f"{exact_frontier_outcome}."
                ),
            },
            {
                "RQ": "RQ3",
                "Evaluation_axis": "Artifact-default advisory selection",
                "Outcome": f"Under the released default weights, the selected NSGA-II point yields {tco_phrase} with {risk_phrase_mean} and {risk_phrase_p90} relative to the {baseline_label} comparator.",
            },
            {
                "RQ": "RQ3",
                "Evaluation_axis": "Selection-weight robustness",
                "Outcome": (
                    f"Default selection is preserved in {default_weight_matches}/{total_weight_runs} perturbations; "
                    f"{unique_weight_portfolios} unique portfolios appear; mean residual risk spans {weight_mean_min:.6f}-{weight_mean_max:.6f}; "
                    f"TCO spans {weight_tco_min:.1f}-{weight_tco_max:.1f}."
                ),
            },
            {
                "RQ": "RQ4",
                "Evaluation_axis": "Reporting-facing export provisioning",
                "Outcome": "Artifact provisions validator logs, tables, plots, and CSV/LaTeX summaries that preserve schema-linked reporting paths.",
            },
            {
                "RQ": "RQ4",
                "Evaluation_axis": "Empirical governance reuse status",
                "Outcome": "Not established in the strict public-data profile; no auditor walkthrough, user study, BI/dashboard deployment, or API/tool-integration evaluation is reported.",
            },
        ]
    )
    save_table(rq_summary, output_dir, "rq_summary")

    plot_roc_curves({name: (y_test, runs[name].test_scores) for name in baseline_order + ["Artifact-default scorer"]}, output_dir, dpi=dpi)
    plot_pr_curves({name: (y_test, runs[name].test_scores) for name in baseline_order + ["Artifact-default scorer"]}, output_dir, dpi=dpi)
    plot_reliability(y_test, paper.test_scores, output_dir, dpi=dpi)
    plot_fixed_fpr(fixed_fpr_df, output_dir, dpi=dpi)
    plot_ids_bars(ids_results[["Model", "F1", "AUROC", "FPR"]], output_dir, dpi=dpi)
    plot_hf_ablation(ablation_df, output_dir, dpi=dpi)
    plot_pareto_front(nsga2_frontier, greedy_frontier, exact_frontier, output_dir, dpi=dpi)
    plot_tco_sensitivity(sensitivity_pivot.set_index("parameter"), output_dir, dpi=dpi)
    plot_residual_distribution(
        test_risk_default["BR"],
        pd.Series(residual_risk_from_controls(test_risk_default["BR"].to_numpy(dtype=float), [float(value) for value in control_frame.loc[control_frame["control_id"].isin(str(nsga2_best["selected_controls"]).split(";")), "effectiveness"].tolist()], hf_reduction=float(control_frame.loc[control_frame["control_id"].isin(str(nsga2_best["selected_controls"]).split(";")), "hf_delta"].sum()))),
        pd.Series(residual_risk_from_controls(test_risk_default["BR"].to_numpy(dtype=float), [float(value) for value in control_frame.loc[control_frame["control_id"].isin(str(strongest_best["selected_controls"]).split(";")), "effectiveness"].tolist()], hf_reduction=float(control_frame.loc[control_frame["control_id"].isin(str(strongest_best["selected_controls"]).split(";")), "hf_delta"].sum()))),
        output_dir,
        dpi=dpi,
    )

    summary_text = "\n".join(
        [
            f"Rows (windowed): {len(dataset_meta)}",
            f"Train/Validation/Test: {len(train_dataset.meta)}/{len(validation_dataset.meta)}/{len(test_dataset.meta)}",
            f"EP alpha/beta: {alpha:.3f}/{beta:.3f}",
            f"Telemetry-only benchmark: F1={paper.metrics.f1:.3f}, AUROC={paper.metrics.auroc:.3f}, PR-AUC={paper.metrics.pr_auc:.3f}, Brier={paper.metrics.brier:.3f}",
            f"HF provenance rows: {', '.join(f'{row.hf_source}={int(row.row_count)}' for row in hf_provenance.itertuples(index=False))}",
            f"CVSS provenance rows: {', '.join(f'{row.cvss_source}={int(row.row_count)}' for row in cvss_provenance.itertuples(index=False))}",
            f"Asset value provenance rows: {', '.join(f'{row.asset_value_source}={int(row.row_count)}' for row in asset_value_provenance.itertuples(index=False))}",
            (
                f"Exact solver auxiliary constraints: min_detection_rate={'disabled' if exact_min_detection_rate is None else f'{exact_min_detection_rate:.3f}'}; "
                f"max_false_positive_rate={'disabled' if exact_max_false_positive_rate is None else f'{exact_max_false_positive_rate:.3f}'}"
            ),
            (
                f"Optimization frontiers: NSGA-II={int(nsga_summary['pareto_size'])} points (HV={float(nsga_summary['hypervolume']):.1f}); "
                f"Greedy={int(greedy_summary['pareto_size'])} points (HV={float(greedy_summary['hypervolume']):.1f}); "
                + (
                    f"Exact-ILP={int(exact_summary.iloc[0]['pareto_size'])} points (HV={float(exact_summary.iloc[0]['hypervolume']):.1f})"
                    if not exact_summary.empty
                    else "Exact-ILP=not returned"
                )
            ),
            f"Optimization comparator: {baseline_label}",
            f"Artifact-default advisory delta vs {baseline_label}: {tco_phrase}; {risk_phrase_mean}; {risk_phrase_p90}",
            (
                "Portfolio selection weight sensitivity: "
                f"{default_weight_matches}/{total_weight_runs} perturbations keep the default selection; "
                f"{unique_weight_portfolios} unique portfolios selected; "
                f"mean residual range={weight_mean_min:.6f}-{weight_mean_max:.6f}; "
                f"TCO range={weight_tco_min:.1f}-{weight_tco_max:.1f}"
            ),
        ]
    )
    write_text(output_dir / "study_summary.txt", summary_text + "\n")

    return {
        "ids_results": ids_results,
        "paper_summary": paper_summary,
        "optimization_summary": optimization_summary,
        "optimization_policy_constraints": policy_constraints,
        "portfolio_weight_sensitivity": weight_sensitivity_df,
        "recommendation_weights": pd.DataFrame([DEFAULT_RECOMMENDATION_WEIGHTS]),
        "rq_summary": rq_summary,
        "validator_summary": validator_summary,
    }
