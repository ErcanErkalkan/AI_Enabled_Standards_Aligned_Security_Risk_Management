from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


META_COLUMNS = {
    "timestamp",
    "asset_id",
    "asset_id_source",
    "label",
    "event_type",
    "cve_id",
    "cvss_source",
    "hf_source",
    "asset_value_source",
}

RISK_ONLY_COLUMNS = {
    "asset_value_raw",
    "cvss_exploitability",
    "cvss_c",
    "cvss_i",
    "cvss_a",
    "hf_failure_ratio",
    "hf_policy_violations",
    "hf_training_gap",
}


@dataclass
class WindowedDataset:
    X_seq: np.ndarray
    X_tab: np.ndarray
    y: np.ndarray
    meta: pd.DataFrame
    feature_names: list[str]


def infer_feature_columns(frame: pd.DataFrame) -> list[str]:
    feature_columns: list[str] = []
    for column in frame.columns:
        if column in META_COLUMNS or column in RISK_ONLY_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(frame[column]):
            feature_columns.append(column)
    return feature_columns


def build_window_dataset(frame: pd.DataFrame, window_size: int, feature_columns: Iterable[str] | None = None) -> WindowedDataset:
    frame = frame.sort_values(["asset_id", "timestamp"]).reset_index(drop=True)
    feature_columns = list(feature_columns or infer_feature_columns(frame))
    X_seq: list[np.ndarray] = []
    X_tab: list[np.ndarray] = []
    y: list[int] = []
    meta_rows: list[dict[str, object]] = []

    for asset_id, group in frame.groupby("asset_id", sort=False):
        group = group.reset_index(drop=True)
        if len(group) < window_size:
            continue
        values = group[feature_columns].to_numpy(dtype=float)
        for end_index in range(window_size - 1, len(group)):
            start_index = end_index - window_size + 1
            window = values[start_index : end_index + 1]
            last_row = window[-1]
            summary = np.concatenate([window.mean(axis=0), window.std(axis=0), last_row], axis=0)
            row = group.iloc[end_index]
            X_seq.append(window)
            X_tab.append(summary)
            y.append(int(row["label"]))
            meta_rows.append(
                {
                    "timestamp": row["timestamp"],
                    "window_start_timestamp": group.iloc[start_index]["timestamp"],
                    "window_end_timestamp": row["timestamp"],
                    "asset_id": asset_id,
                    "asset_id_source": row.get("asset_id_source", "provided"),
                    "label": int(row["label"]),
                    "event_type": row["event_type"],
                    "cve_id": row["cve_id"],
                    "hf_source": row.get("hf_source", "HF:none"),
                    "cvss_source": row.get("cvss_source", "unknown"),
                    "asset_value_source": row.get("asset_value_source", "provided"),
                    "asset_value_raw": float(row["asset_value_raw"]),
                    "cvss_exploitability": float(row["cvss_exploitability"]),
                    "cvss_c": float(row["cvss_c"]),
                    "cvss_i": float(row["cvss_i"]),
                    "cvss_a": float(row["cvss_a"]),
                    "hf_failure_ratio": float(row["hf_failure_ratio"]),
                    "hf_policy_violations": float(row["hf_policy_violations"]),
                    "hf_training_gap": float(row["hf_training_gap"]),
                }
            )

    return WindowedDataset(
        X_seq=np.asarray(X_seq, dtype=np.float32),
        X_tab=np.asarray(X_tab, dtype=np.float32),
        y=np.asarray(y, dtype=np.int64),
        meta=pd.DataFrame(meta_rows).sort_values("timestamp").reset_index(drop=True),
        feature_names=feature_columns,
    )


def _align_split_to_asset_boundary(
    ordered: pd.DataFrame,
    split_index: int,
    lower_bound: int,
    upper_bound: int,
) -> int:
    if split_index <= lower_bound or split_index >= upper_bound or split_index <= 0 or split_index >= len(ordered):
        return split_index
    previous_asset = ordered.iloc[split_index - 1]["asset_id"]
    next_asset = ordered.iloc[split_index]["asset_id"]
    if previous_asset != next_asset:
        return split_index
    run_start = split_index - 1
    while run_start > 0 and ordered.iloc[run_start - 1]["asset_id"] == previous_asset:
        run_start -= 1
    run_end = split_index
    while run_end < len(ordered) and ordered.iloc[run_end]["asset_id"] == previous_asset:
        run_end += 1
    candidates = [candidate for candidate in (run_start, run_end) if lower_bound <= candidate <= upper_bound]
    if not candidates:
        return split_index
    return min(candidates, key=lambda candidate: (abs(candidate - split_index), candidate))


def chronological_frame_splits(
    frame: pd.DataFrame,
    validation_fraction: float,
    test_fraction: float,
    *,
    align_on_asset_boundaries: bool = False,
) -> dict[str, pd.DataFrame]:
    if validation_fraction < 0.0 or test_fraction < 0.0 or validation_fraction + test_fraction >= 1.0:
        raise ValueError("validation_fraction and test_fraction must be non-negative and sum to less than 1.0.")
    ordered = frame.sort_values(["timestamp", "asset_id"]).reset_index(drop=True)
    n_rows = len(ordered)
    test_start = int(np.floor(n_rows * (1.0 - test_fraction)))
    val_start = int(np.floor(n_rows * (1.0 - test_fraction - validation_fraction)))
    test_start = min(max(test_start, 0), n_rows)
    val_start = min(max(val_start, 0), test_start)
    if align_on_asset_boundaries and "asset_id" in ordered.columns and n_rows:
        val_start = _align_split_to_asset_boundary(ordered, val_start, lower_bound=0, upper_bound=test_start)
        test_start = _align_split_to_asset_boundary(ordered, test_start, lower_bound=val_start, upper_bound=n_rows)
    return {
        "train": ordered.iloc[:val_start].copy(),
        "validation": ordered.iloc[val_start:test_start].copy(),
        "test": ordered.iloc[test_start:].copy(),
    }


def chronological_split_indices(meta: pd.DataFrame, validation_fraction: float, test_fraction: float) -> dict[str, np.ndarray]:
    ordered = meta.reset_index().rename(columns={"index": "row_index"})
    split_frames = chronological_frame_splits(ordered, validation_fraction=validation_fraction, test_fraction=test_fraction)
    return {name: split_frame["row_index"].to_numpy() for name, split_frame in split_frames.items()}


def expanding_time_group_folds(meta: pd.DataFrame, n_folds: int) -> list[tuple[np.ndarray, np.ndarray]]:
    ordered = meta.sort_values(["timestamp", "asset_id"]).reset_index().rename(columns={"index": "row_index"})
    group_frame = (
        ordered.groupby("asset_id", sort=False)
        .agg(group_start=("timestamp", "min"), group_end=("timestamp", "max"), row_count=("row_index", "size"))
        .reset_index()
        .sort_values(["group_start", "group_end", "asset_id"])
        .reset_index(drop=True)
    )
    group_blocks = [block for block in np.array_split(group_frame.index.to_numpy(), n_folds + 1) if len(block)]
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for fold_index in range(min(n_folds, len(group_blocks) - 1)):
        train_group_index = np.concatenate(group_blocks[: fold_index + 1])
        validation_group_index = group_blocks[fold_index + 1]
        train_assets = set(group_frame.loc[train_group_index, "asset_id"])
        validation_assets = set(group_frame.loc[validation_group_index, "asset_id"])
        validation_start = group_frame.loc[validation_group_index, "group_start"].min()
        train_index = ordered.loc[
            ordered["asset_id"].isin(train_assets) & (ordered["timestamp"] < validation_start),
            "row_index",
        ].to_numpy()
        validation_index = ordered.loc[ordered["asset_id"].isin(validation_assets), "row_index"].to_numpy()
        if len(train_index) and len(validation_index):
            folds.append((train_index, validation_index))
    return folds
