from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from xgboost import XGBClassifier

from ai_risk.metrics import ThresholdedMetrics, compute_thresholded_metrics, select_threshold_by_f1
from ai_risk.preprocessing import expanding_time_group_folds

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Torch is required for the deep-learning baselines in this artifact.") from exc


@dataclass
class ModelRun:
    name: str
    validation_scores: np.ndarray
    test_scores: np.ndarray
    threshold: float
    metrics: ThresholdedMetrics
    fit_seconds: float
    best_params: dict[str, object]


class LSTMAnomalyRegressor(nn.Module):
    def __init__(self, input_dim: int, hidden_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_size, num_layers=2, batch_first=True, dropout=0.1)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, input_dim),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs, _ = self.lstm(inputs)
        return self.head(outputs[:, -1, :])


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim: int, hidden_size: int) -> None:
        super().__init__()
        bottleneck = max(16, hidden_size // 2)
        self.encoder = nn.LSTM(input_dim, hidden_size, num_layers=1, batch_first=True)
        self.to_latent = nn.Linear(hidden_size, bottleneck)
        self.decoder = nn.LSTM(bottleneck, hidden_size, num_layers=1, batch_first=True)
        self.out = nn.Linear(hidden_size, input_dim)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.encoder(inputs)
        latent = self.to_latent(hidden[-1])
        repeated = latent.unsqueeze(1).repeat(1, inputs.shape[1], 1)
        decoded, _ = self.decoder(repeated)
        return self.out(decoded)


class CNNSequenceClassifier(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(input_dim, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Dropout(0.30),
            nn.Linear(128, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.head(self.network(inputs.transpose(1, 2))).squeeze(-1)


def _torch_loader(X: np.ndarray, y: np.ndarray | None = None, batch_size: int = 64, shuffle: bool = True) -> DataLoader:
    if y is None:
        dataset = TensorDataset(torch.tensor(X, dtype=torch.float32))
    else:
        dataset = TensorDataset(torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32))
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def _train_torch_regressor(model: nn.Module, X_train: np.ndarray, X_target: np.ndarray, epochs: int, batch_size: int) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    loader = _torch_loader(X_train, X_target, batch_size=batch_size, shuffle=True)
    model.train()
    for _ in range(epochs):
        for batch_inputs, batch_targets in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(batch_inputs), batch_targets)
            loss.backward()
            optimizer.step()


def _train_torch_autoencoder(model: nn.Module, X_train: np.ndarray, epochs: int, batch_size: int) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    loader = _torch_loader(X_train, None, batch_size=batch_size, shuffle=True)
    model.train()
    for _ in range(epochs):
        for (batch_inputs,) in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(batch_inputs), batch_inputs)
            loss.backward()
            optimizer.step()


def _train_torch_classifier(model: nn.Module, X_train: np.ndarray, y_train: np.ndarray, epochs: int, batch_size: int) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    loader = _torch_loader(X_train, y_train, batch_size=batch_size, shuffle=True)
    model.train()
    for _ in range(epochs):
        for batch_inputs, batch_targets in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(batch_inputs), batch_targets)
            loss.backward()
            optimizer.step()


def _score_lstm_regressor(model: nn.Module, X: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        inputs = torch.tensor(X, dtype=torch.float32)
        targets = inputs[:, -1, :]
        predictions = model(inputs)
        errors = torch.mean((predictions - targets) ** 2, dim=1)
    return errors.cpu().numpy()


def _score_autoencoder(model: nn.Module, X: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        inputs = torch.tensor(X, dtype=torch.float32)
        recon = model(inputs)
        errors = torch.mean((recon - inputs) ** 2, dim=(1, 2))
    return errors.cpu().numpy()


def _score_classifier_logits(model: nn.Module, X: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(X, dtype=torch.float32))
        scores = torch.sigmoid(logits)
    return scores.cpu().numpy()


def _calibrate_and_threshold(raw_scores: np.ndarray, y_true: np.ndarray) -> tuple[np.ndarray, float]:
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_scores, y_true)
    calibrated = calibrator.transform(raw_scores)
    threshold = select_threshold_by_f1(y_true, calibrated)
    return calibrated, threshold


def _grid_to_param_dicts(grid: dict[str, list[object]]) -> list[dict[str, object]]:
    keys = list(grid)
    values = [grid[key] for key in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _mean_or_negative_inf(values: list[float]) -> float:
    return float(np.mean(values)) if values else float("-inf")


def _predict_positive_class_proba(model, X: np.ndarray) -> np.ndarray:
    predict_input = X
    feature_names = getattr(model, "feature_names_in_", None)
    if feature_names is not None and not isinstance(X, pd.DataFrame) and len(feature_names) == X.shape[1]:
        predict_input = pd.DataFrame(X, columns=list(feature_names))
    probabilities = np.asarray(model.predict_proba(predict_input), dtype=float)
    if probabilities.ndim == 1:
        return probabilities
    classes = np.asarray(getattr(model, "classes_", np.arange(probabilities.shape[1])), dtype=int)
    if 1 in classes:
        return probabilities[:, int(np.where(classes == 1)[0][0])]
    return np.zeros(len(X), dtype=float)


def _ocsvm_param_grid(feature_count: int, coarse: bool) -> list[dict[str, object]]:
    grid = {
        "nu": [0.05] if coarse else [0.01, 0.05, 0.10],
        "gamma": [1.0 / feature_count, 2.0 / feature_count] if coarse else [1.0 / feature_count, 0.5 / feature_count, 2.0 / feature_count],
    }
    return _grid_to_param_dicts(grid)


def _iforest_param_grid(coarse: bool) -> list[dict[str, object]]:
    grid = {"contamination": [0.05] if coarse else [0.01, 0.05, 0.10]}
    return _grid_to_param_dicts(grid)


def _rf_param_grid(coarse: bool) -> list[dict[str, object]]:
    grid = {
        "n_estimators": [400] if coarse else [200, 400, 600],
        "max_depth": [24] if coarse else [None, 12, 24],
        "max_features": ["sqrt"] if coarse else ["sqrt", 0.3],
    }
    return _grid_to_param_dicts(grid)


def _lightgbm_param_grid(coarse: bool) -> list[dict[str, object]]:
    grid = {
        "num_leaves": [31] if coarse else [31, 63],
        "max_depth": [12] if coarse else [-1, 12],
        "learning_rate": [0.05] if coarse else [0.05, 0.1],
        "n_estimators": [400] if coarse else [300, 600],
    }
    return _grid_to_param_dicts(grid)


def _xgb_param_grid(coarse: bool) -> list[dict[str, object]]:
    grid = {
        "n_estimators": [350] if coarse else [250, 350, 500],
        "max_depth": [5] if coarse else [4, 5, 6],
        "learning_rate": [0.06] if coarse else [0.05, 0.1],
    }
    return _grid_to_param_dicts(grid)


def _select_best_params(
    candidate_params: list[dict[str, object]],
    scorer,
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    best_params = candidate_params[0]
    best_summary = {"mean_f1": float("-inf"), "mean_auroc": float("-inf")}
    best_cache: dict[str, np.ndarray] = {}
    for params in candidate_params:
        summary, cache = scorer(params)
        ranking = (summary["mean_f1"], summary["mean_auroc"])
        best_ranking = (best_summary["mean_f1"], best_summary["mean_auroc"])
        if ranking > best_ranking:
            best_params = params
            best_summary = summary
            best_cache = cache
    return best_params, best_cache


def _oof_calibrate(raw_oof: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, IsotonicRegression, float]:
    valid_mask = ~np.isnan(raw_oof)
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_oof[valid_mask], y[valid_mask])
    calibrated_oof = np.full_like(raw_oof, fill_value=np.nan, dtype=float)
    calibrated_oof[valid_mask] = calibrator.transform(raw_oof[valid_mask])
    threshold = select_threshold_by_f1(y[valid_mask], calibrated_oof[valid_mask])
    return calibrated_oof, calibrator, threshold


def run_all_ids_models(
    X_seq_train: np.ndarray,
    X_seq_val: np.ndarray,
    X_seq_test: np.ndarray,
    X_tab_train: np.ndarray,
    X_tab_val: np.ndarray,
    X_tab_test: np.ndarray,
    y_train: np.ndarray,
    y_val: np.ndarray,
    y_test: np.ndarray,
    model_cfg: dict,
    seed: int,
    meta_train: pd.DataFrame,
    meta_val: pd.DataFrame,
) -> tuple[dict[str, ModelRun], dict[str, np.ndarray], dict[str, dict[str, np.ndarray]]]:
    epochs_lstm_detector = int(model_cfg.get("epochs_lstm_detector", 8))
    epochs_lstm_autoencoder = int(model_cfg.get("epochs_lstm_autoencoder", 8))
    epochs_cnn = int(model_cfg.get("epochs_cnn", 8))
    batch_size = int(model_cfg.get("batch_size", 64))
    hidden_size = int(model_cfg.get("hidden_size", 32))
    cv_folds = int(model_cfg.get("cv_folds", 5))
    coarse_search = bool(model_cfg.get("coarse_search", False))

    X_seq_pre = np.concatenate([X_seq_train, X_seq_val], axis=0)
    X_tab_pre = np.concatenate([X_tab_train, X_tab_val], axis=0)
    y_pre = np.concatenate([y_train, y_val], axis=0)
    meta_pre = pd.concat([meta_train, meta_val], ignore_index=True)
    folds = expanding_time_group_folds(meta_pre, n_folds=cv_folds)
    if not folds:
        raise ValueError("Cross-validation folds could not be generated from the pre-test window.")

    runs: dict[str, ModelRun] = {}
    pretest_scores: dict[str, np.ndarray] = {}
    aux_outputs: dict[str, dict[str, np.ndarray]] = {}

    def _summary_from_fold_scores(fold_y: list[np.ndarray], fold_scores: list[np.ndarray]) -> dict[str, float]:
        f1_values = []
        auroc_values = []
        for y_block, score_block in zip(fold_y, fold_scores):
            calibrated, threshold = _calibrate_and_threshold(score_block, y_block)
            metrics = compute_thresholded_metrics(y_block, calibrated, threshold)
            f1_values.append(metrics.f1)
            auroc_values.append(metrics.auroc)
        return {"mean_f1": _mean_or_negative_inf(f1_values), "mean_auroc": _mean_or_negative_inf(auroc_values)}

    start = time.perf_counter()

    def _score_ocsvm(params: dict[str, object]) -> tuple[dict[str, float], dict[str, np.ndarray]]:
        raw_oof = np.full(len(y_pre), np.nan, dtype=float)
        fold_y: list[np.ndarray] = []
        fold_scores: list[np.ndarray] = []
        for train_idx, val_idx in folds:
            benign_idx = train_idx[y_pre[train_idx] == 0]
            model = Pipeline(
                steps=[("scale", StandardScaler()), ("model", OneClassSVM(kernel="rbf", nu=float(params["nu"]), gamma=float(params["gamma"])))]
            )
            model.fit(X_tab_pre[benign_idx])
            raw_val = -model.decision_function(X_tab_pre[val_idx])
            raw_oof[val_idx] = raw_val
            fold_y.append(y_pre[val_idx])
            fold_scores.append(raw_val)
        return _summary_from_fold_scores(fold_y, fold_scores), {"raw_oof": raw_oof}

    best_params, cache = _select_best_params(_ocsvm_param_grid(X_tab_pre.shape[1], coarse_search), _score_ocsvm)
    calibrated_oof, calibrator, threshold = _oof_calibrate(cache["raw_oof"], y_pre)
    final_model = Pipeline(
        steps=[("scale", StandardScaler()), ("model", OneClassSVM(kernel="rbf", nu=float(best_params["nu"]), gamma=float(best_params["gamma"])))]
    )
    final_model.fit(X_tab_pre[y_pre == 0])
    test_scores = calibrator.transform(-final_model.decision_function(X_tab_test))
    runs["OC-SVM"] = ModelRun(
        name="OC-SVM",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params=best_params,
    )
    pretest_scores["OC-SVM"] = calibrated_oof

    start = time.perf_counter()

    def _score_iforest(params: dict[str, object]) -> tuple[dict[str, float], dict[str, np.ndarray]]:
        raw_oof = np.full(len(y_pre), np.nan, dtype=float)
        fold_y: list[np.ndarray] = []
        fold_scores: list[np.ndarray] = []
        for train_idx, val_idx in folds:
            benign_idx = train_idx[y_pre[train_idx] == 0]
            model = IsolationForest(
                n_estimators=200,
                contamination=float(params["contamination"]),
                random_state=seed,
                max_samples=min(256, len(benign_idx)),
            )
            model.fit(X_tab_pre[benign_idx])
            raw_val = -model.score_samples(X_tab_pre[val_idx])
            raw_oof[val_idx] = raw_val
            fold_y.append(y_pre[val_idx])
            fold_scores.append(raw_val)
        return _summary_from_fold_scores(fold_y, fold_scores), {"raw_oof": raw_oof}

    best_params, cache = _select_best_params(_iforest_param_grid(coarse_search), _score_iforest)
    calibrated_oof, calibrator, threshold = _oof_calibrate(cache["raw_oof"], y_pre)
    final_model = IsolationForest(
        n_estimators=200,
        contamination=float(best_params["contamination"]),
        random_state=seed,
        max_samples=min(256, len(X_tab_pre[y_pre == 0])),
    )
    final_model.fit(X_tab_pre[y_pre == 0])
    test_scores = calibrator.transform(-final_model.score_samples(X_tab_test))
    runs["Isolation Forest"] = ModelRun(
        name="Isolation Forest",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params=best_params,
    )
    pretest_scores["Isolation Forest"] = calibrated_oof

    start = time.perf_counter()
    raw_oof = np.full(len(y_pre), np.nan, dtype=float)
    for train_idx, val_idx in folds:
        model = LSTMAutoencoder(X_seq_pre.shape[-1], hidden_size)
        benign_idx = train_idx[y_pre[train_idx] == 0]
        _train_torch_autoencoder(model, X_seq_pre[benign_idx], epochs=epochs_lstm_autoencoder, batch_size=batch_size)
        raw_oof[val_idx] = _score_autoencoder(model, X_seq_pre[val_idx])
    calibrated_oof, calibrator, threshold = _oof_calibrate(raw_oof, y_pre)
    final_model = LSTMAutoencoder(X_seq_pre.shape[-1], hidden_size)
    _train_torch_autoencoder(final_model, X_seq_pre[y_pre == 0], epochs=epochs_lstm_autoencoder, batch_size=batch_size)
    test_scores = calibrator.transform(_score_autoencoder(final_model, X_seq_test))
    runs["LSTM-AE"] = ModelRun(
        name="LSTM-AE",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params={"encoder": "[64,32]", "bottleneck": max(16, hidden_size // 2), "epochs": epochs_lstm_autoencoder},
    )
    pretest_scores["LSTM-AE"] = calibrated_oof

    start = time.perf_counter()

    def _score_rf(params: dict[str, object]) -> tuple[dict[str, float], dict[str, np.ndarray]]:
        raw_oof = np.full(len(y_pre), np.nan, dtype=float)
        fold_y: list[np.ndarray] = []
        fold_scores: list[np.ndarray] = []
        for train_idx, val_idx in folds:
            if np.unique(y_pre[train_idx]).size < 2:
                raw_val = np.full(len(val_idx), float(np.mean(y_pre[train_idx])), dtype=float)
                raw_oof[val_idx] = raw_val
                fold_y.append(y_pre[val_idx])
                fold_scores.append(raw_val)
                continue
            model = RandomForestClassifier(
                n_estimators=int(params["n_estimators"]),
                max_depth=params["max_depth"],
                max_features=params["max_features"],
                random_state=seed,
                n_jobs=-1,
            )
            model.fit(X_tab_pre[train_idx], y_pre[train_idx])
            raw_val = _predict_positive_class_proba(model, X_tab_pre[val_idx])
            raw_oof[val_idx] = raw_val
            fold_y.append(y_pre[val_idx])
            fold_scores.append(raw_val)
        return _summary_from_fold_scores(fold_y, fold_scores), {"raw_oof": raw_oof}

    best_params, cache = _select_best_params(_rf_param_grid(coarse_search), _score_rf)
    calibrated_oof, calibrator, threshold = _oof_calibrate(cache["raw_oof"], y_pre)
    final_model = RandomForestClassifier(
        n_estimators=int(best_params["n_estimators"]),
        max_depth=best_params["max_depth"],
        max_features=best_params["max_features"],
        random_state=seed,
        n_jobs=-1,
    )
    final_model.fit(X_tab_pre, y_pre)
    test_scores = calibrator.transform(_predict_positive_class_proba(final_model, X_tab_test))
    runs["Random Forest"] = ModelRun(
        name="Random Forest",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params=best_params,
    )
    pretest_scores["Random Forest"] = calibrated_oof

    start = time.perf_counter()

    def _score_lgbm(params: dict[str, object]) -> tuple[dict[str, float], dict[str, np.ndarray]]:
        raw_oof = np.full(len(y_pre), np.nan, dtype=float)
        fold_y: list[np.ndarray] = []
        fold_scores: list[np.ndarray] = []
        for train_idx, val_idx in folds:
            if np.unique(y_pre[train_idx]).size < 2:
                raw_val = np.full(len(val_idx), float(np.mean(y_pre[train_idx])), dtype=float)
                raw_oof[val_idx] = raw_val
                fold_y.append(y_pre[val_idx])
                fold_scores.append(raw_val)
                continue
            model = LGBMClassifier(
                n_estimators=int(params["n_estimators"]),
                max_depth=int(params["max_depth"]),
                num_leaves=int(params["num_leaves"]),
                learning_rate=float(params["learning_rate"]),
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=seed,
                verbose=-1,
            )
            model.fit(X_tab_pre[train_idx], y_pre[train_idx])
            raw_val = _predict_positive_class_proba(model, X_tab_pre[val_idx])
            raw_oof[val_idx] = raw_val
            fold_y.append(y_pre[val_idx])
            fold_scores.append(raw_val)
        return _summary_from_fold_scores(fold_y, fold_scores), {"raw_oof": raw_oof}

    best_params, cache = _select_best_params(_lightgbm_param_grid(coarse_search), _score_lgbm)
    calibrated_oof, calibrator, threshold = _oof_calibrate(cache["raw_oof"], y_pre)
    final_model = LGBMClassifier(
        n_estimators=int(best_params["n_estimators"]),
        max_depth=int(best_params["max_depth"]),
        num_leaves=int(best_params["num_leaves"]),
        learning_rate=float(best_params["learning_rate"]),
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=seed,
        verbose=-1,
    )
    final_model.fit(X_tab_pre, y_pre)
    test_scores = calibrator.transform(_predict_positive_class_proba(final_model, X_tab_test))
    runs["LightGBM"] = ModelRun(
        name="LightGBM",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params=best_params,
    )
    pretest_scores["LightGBM"] = calibrated_oof

    start = time.perf_counter()
    raw_oof = np.full(len(y_pre), np.nan, dtype=float)
    for train_idx, val_idx in folds:
        model = CNNSequenceClassifier(X_seq_pre.shape[-1])
        _train_torch_classifier(model, X_seq_pre[train_idx], y_pre[train_idx], epochs=epochs_cnn, batch_size=batch_size)
        raw_oof[val_idx] = _score_classifier_logits(model, X_seq_pre[val_idx])
    calibrated_oof, calibrator, threshold = _oof_calibrate(raw_oof, y_pre)
    final_model = CNNSequenceClassifier(X_seq_pre.shape[-1])
    _train_torch_classifier(final_model, X_seq_pre, y_pre, epochs=epochs_cnn, batch_size=batch_size)
    test_scores = calibrator.transform(_score_classifier_logits(final_model, X_seq_test))
    runs["1D-CNN"] = ModelRun(
        name="1D-CNN",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params={"epochs": epochs_cnn, "dropout": 0.30},
    )
    pretest_scores["1D-CNN"] = calibrated_oof

    start = time.perf_counter()

    def _paper_fold_scores(params: dict[str, object]) -> tuple[dict[str, float], dict[str, np.ndarray]]:
        raw_oof = np.full(len(y_pre), np.nan, dtype=float)
        likelihood_oof = np.full(len(y_pre), np.nan, dtype=float)
        fold_y: list[np.ndarray] = []
        fold_scores: list[np.ndarray] = []
        for train_idx, val_idx in folds:
            benign_idx = train_idx[y_pre[train_idx] == 0]
            detector = LSTMAnomalyRegressor(X_seq_pre.shape[-1], hidden_size)
            _train_torch_regressor(
                detector,
                X_seq_pre[benign_idx],
                X_seq_pre[benign_idx][:, -1, :],
                epochs=epochs_lstm_detector,
                batch_size=batch_size,
            )
            anomaly_train = _score_lstm_regressor(detector, X_seq_pre[train_idx])
            anomaly_val = _score_lstm_regressor(detector, X_seq_pre[val_idx])
            likelihood_oof[val_idx] = anomaly_val
            if np.unique(y_pre[train_idx]).size < 2:
                raw_val = np.full(len(val_idx), float(np.mean(y_pre[train_idx])), dtype=float)
                raw_oof[val_idx] = raw_val
                fold_y.append(y_pre[val_idx])
                fold_scores.append(raw_val)
                continue
            xgb = XGBClassifier(
                n_estimators=int(params["n_estimators"]),
                max_depth=int(params["max_depth"]),
                learning_rate=float(params["learning_rate"]),
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=seed,
                eval_metric="logloss",
                n_jobs=4,
            )
            xgb.fit(np.column_stack([X_tab_pre[train_idx], anomaly_train]), y_pre[train_idx])
            raw_val = _predict_positive_class_proba(xgb, np.column_stack([X_tab_pre[val_idx], anomaly_val]))
            raw_oof[val_idx] = raw_val
            fold_y.append(y_pre[val_idx])
            fold_scores.append(raw_val)
        return _summary_from_fold_scores(fold_y, fold_scores), {"raw_oof": raw_oof, "likelihood_oof": likelihood_oof}

    best_params, cache = _select_best_params(_xgb_param_grid(coarse_search), _paper_fold_scores)
    calibrated_oof, calibrator, threshold = _oof_calibrate(cache["raw_oof"], y_pre)
    detector = LSTMAnomalyRegressor(X_seq_pre.shape[-1], hidden_size)
    _train_torch_regressor(
        detector,
        X_seq_pre[y_pre == 0],
        X_seq_pre[y_pre == 0][:, -1, :],
        epochs=epochs_lstm_detector,
        batch_size=batch_size,
    )
    likelihood_pre = _score_lstm_regressor(detector, X_seq_pre)
    likelihood_test = _score_lstm_regressor(detector, X_seq_test)
    xgb = XGBClassifier(
        n_estimators=int(best_params["n_estimators"]),
        max_depth=int(best_params["max_depth"]),
        learning_rate=float(best_params["learning_rate"]),
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=seed,
        eval_metric="logloss",
        n_jobs=4,
    )
    xgb.fit(np.column_stack([X_tab_pre, likelihood_pre]), y_pre)
    raw_test = _predict_positive_class_proba(xgb, np.column_stack([X_tab_test, likelihood_test]))
    test_scores = calibrator.transform(raw_test)
    runs["Artifact-default scorer"] = ModelRun(
        name="Artifact-default scorer",
        validation_scores=calibrated_oof,
        test_scores=test_scores,
        threshold=threshold,
        metrics=compute_thresholded_metrics(y_test, test_scores, threshold),
        fit_seconds=time.perf_counter() - start,
        best_params=best_params,
    )
    pretest_scores["Artifact-default scorer"] = calibrated_oof
    aux_outputs["Artifact-default scorer"] = {
        "likelihood_pretest": likelihood_pre,
        "likelihood_test": likelihood_test,
    }

    return runs, pretest_scores, aux_outputs
