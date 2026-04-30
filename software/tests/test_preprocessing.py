from __future__ import annotations

import pandas as pd

from ai_risk.preprocessing import build_window_dataset, chronological_frame_splits, expanding_time_group_folds


def test_expanding_time_group_folds_keep_assets_disjoint_and_forward_in_time():
    rows = []
    for asset_index, asset_id in enumerate(["asset_a", "asset_b", "asset_c", "asset_d"]):
        start = pd.Timestamp("2025-01-01 00:00:00") + pd.Timedelta(minutes=asset_index * 5)
        for step in range(6):
            rows.append(
                {
                    "timestamp": start + pd.Timedelta(minutes=step * 10),
                    "asset_id": asset_id,
                }
            )
    meta = pd.DataFrame(rows)

    folds = expanding_time_group_folds(meta, n_folds=3)

    assert len(folds) == 3
    for train_index, validation_index in folds:
        train_meta = meta.iloc[train_index]
        validation_meta = meta.iloc[validation_index]
        assert set(train_meta["asset_id"]).isdisjoint(set(validation_meta["asset_id"]))
        assert train_meta["timestamp"].max() < validation_meta["timestamp"].min()


def test_build_window_dataset_excludes_risk_only_numeric_fields_from_model_features():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=4, freq="h"),
            "asset_id": ["asset_a"] * 4,
            "label": [0, 0, 1, 1],
            "event_type": ["benign", "benign", "dos", "dos"],
            "cve_id": ["CVE-0"] * 4,
            "packet_rate": [10.0, 11.0, 20.0, 22.0],
            "byte_rate": [100.0, 110.0, 220.0, 250.0],
            "asset_value_raw": [100000.0, 100000.0, 100000.0, 100000.0],
            "cvss_exploitability": [0.2, 0.2, 0.8, 0.8],
            "cvss_c": [0.1, 0.1, 0.5, 0.5],
            "cvss_i": [0.1, 0.1, 0.5, 0.5],
            "cvss_a": [0.1, 0.1, 0.5, 0.5],
            "hf_failure_ratio": [0.0, 0.0, 0.0, 0.0],
            "hf_policy_violations": [0.0, 0.0, 0.0, 0.0],
            "hf_training_gap": [0.0, 0.0, 0.0, 0.0],
        }
    )

    dataset = build_window_dataset(frame, window_size=2)

    assert dataset.feature_names == ["packet_rate", "byte_rate"]
    assert dataset.X_seq.shape[-1] == 2
    assert {"asset_value_raw", "cvss_exploitability", "hf_failure_ratio"}.isdisjoint(set(dataset.feature_names))


def test_chronological_frame_splits_before_windowing_avoid_cross_split_window_overlap():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=12, freq="h"),
            "asset_id": ["asset_a"] * 12,
            "label": [0] * 12,
            "event_type": ["benign"] * 12,
            "cve_id": ["CVE-0"] * 12,
            "packet_rate": list(range(12)),
            "byte_rate": list(range(100, 112)),
            "asset_value_raw": [100000.0] * 12,
            "cvss_exploitability": [0.2] * 12,
            "cvss_c": [0.1] * 12,
            "cvss_i": [0.1] * 12,
            "cvss_a": [0.1] * 12,
            "hf_failure_ratio": [0.0] * 12,
            "hf_policy_violations": [0.0] * 12,
            "hf_training_gap": [0.0] * 12,
        }
    )

    frame_splits = chronological_frame_splits(frame, validation_fraction=0.25, test_fraction=0.25)
    feature_columns = ["packet_rate", "byte_rate"]
    train_dataset = build_window_dataset(frame_splits["train"], window_size=3, feature_columns=feature_columns)
    validation_dataset = build_window_dataset(frame_splits["validation"], window_size=3, feature_columns=feature_columns)
    test_dataset = build_window_dataset(frame_splits["test"], window_size=3, feature_columns=feature_columns)

    assert train_dataset.meta["window_end_timestamp"].max() < validation_dataset.meta["window_start_timestamp"].min()
    assert validation_dataset.meta["window_end_timestamp"].max() < test_dataset.meta["window_start_timestamp"].min()


def test_chronological_frame_splits_can_align_boundaries_to_asset_changes():
    rows = []
    for asset_id in ["asset_a", "asset_b", "asset_c"]:
        start = pd.Timestamp("2025-01-01") + pd.Timedelta(hours=len(rows))
        for step in range(4):
            rows.append(
                {
                    "timestamp": start + pd.Timedelta(minutes=step),
                    "asset_id": asset_id,
                }
            )
    frame = pd.DataFrame(rows)

    splits = chronological_frame_splits(
        frame,
        validation_fraction=0.25,
        test_fraction=0.25,
        align_on_asset_boundaries=True,
    )

    assert set(splits["train"]["asset_id"]) == {"asset_a"}
    assert set(splits["validation"]["asset_id"]) == {"asset_b"}
    assert set(splits["test"]["asset_id"]) == {"asset_c"}
