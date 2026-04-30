from __future__ import annotations

from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

import numpy as np
import pandas as pd

from ai_risk.demo_data import CVE_PROFILES, generate_demo_dataframe
from ai_risk.nvd import enrich_cves_with_cache


STANDARD_COLUMN_MAP = {
    "label": "label",
    "attack": "event_type",
    "attack_type": "event_type",
    "timestamp": "timestamp",
    "time": "timestamp",
    "flow_duration": "flow_duration",
    "duration": "flow_duration",
    "rate": "packet_rate",
    "srate": "packet_rate",
    "tot_sum": "byte_rate",
    "tot_size": "avg_packet_size",
}

BENIGN_EVENT_ALIASES = {
    "benign",
    "benign_final",
    "benigntraffic",
    "benigntraffic1",
    "benigntraffic2",
    "benigntraffic3",
}

HF_COLUMNS = (
    "hf_failure_ratio",
    "hf_policy_violations",
    "hf_training_gap",
)

HF_SOURCE_NONE = "HF:none"
HF_SOURCE_SIM = "HF:sim"
HF_SOURCE_REAL = "HF:real"

CVE_MAP_KEY_PRIORITY = (
    ("event_type",),
    ("asset_id",),
    ("asset_id", "event_type"),
    ("asset_id", "timestamp"),
    ("asset_id", "timestamp", "event_type"),
)

NEUTRAL_CVE_PROFILE = CVE_PROFILES["recon"]


def load_demo_data(profile_cfg: dict, seed: int) -> pd.DataFrame:
    demo_cfg = profile_cfg.get("demo", {})
    frame = generate_demo_dataframe(
        seed=seed,
        n_assets=int(demo_cfg.get("n_assets", 24)),
        steps_per_asset=int(demo_cfg.get("steps_per_asset", 280)),
        attack_burst_prob=float(demo_cfg.get("benign_attack_burst_prob", 0.08)),
    )
    frame["asset_id_source"] = "provided"
    frame["asset_value_source"] = "provided"
    frame["cvss_source"] = "simulated_event_profile"
    frame["hf_source"] = HF_SOURCE_SIM
    return frame


def _apply_frame_sampling(frame: pd.DataFrame, sample_fraction: float | None, sample_random_state: int) -> pd.DataFrame:
    if sample_fraction is None or sample_fraction >= 1.0 or frame.empty:
        return frame
    if sample_fraction <= 0.0:
        raise ValueError("sample_fraction must be positive when provided.")
    sampled = frame.sample(frac=sample_fraction, random_state=sample_random_state)
    return sampled.reset_index(drop=True)


def _read_csv_files(
    paths: Iterable[Path],
    max_input_files: int | None = None,
    rows_per_input_file: int | None = None,
    sample_fraction: float | None = None,
    sample_random_state: int = 42,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    selected_paths = list(paths)
    if max_input_files is not None:
        selected_paths = selected_paths[:max_input_files]
    for path in selected_paths:
        frame = pd.read_csv(path, nrows=rows_per_input_file)
        frame = _apply_frame_sampling(frame, sample_fraction, sample_random_state)
        frame["__source_file"] = path.name
        frame["__source_parent"] = path.parent.name
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No CSV files were found in data/raw/ciciot2023")
    return pd.concat(frames, ignore_index=True)


def _read_csv_members_from_zip(
    zip_path: Path,
    max_input_files: int | None = None,
    rows_per_input_file: int | None = None,
    sample_fraction: float | None = None,
    sample_random_state: int = 42,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with ZipFile(zip_path) as archive:
        member_names = [
            member_name
            for member_name in archive.namelist()
            if not member_name.endswith("/") and member_name.lower().endswith(".csv")
        ]
        if max_input_files is not None:
            member_names = member_names[:max_input_files]
        for member_name in member_names:
            member_path = Path(member_name)
            with archive.open(member_name) as handle:
                frame = pd.read_csv(handle, nrows=rows_per_input_file)
            frame = _apply_frame_sampling(frame, sample_fraction, sample_random_state)
            frame["__source_file"] = member_path.name
            frame["__source_parent"] = member_path.parent.name
            frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No CSV members were found in archive {zip_path}")
    return pd.concat(frames, ignore_index=True)


def _normalize_event_label(value: object) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return text.replace("__", "_")


def infer_event_family(value: object) -> str:
    label = _normalize_event_label(value)
    if label in BENIGN_EVENT_ALIASES or "benign" in label:
        return "benign"
    if "ddos" in label:
        return "ddos"
    if label.startswith("dos") or "dos_" in label:
        return "dos"
    if "recon" in label or "scan" in label:
        return "recon"
    if any(token in label for token in ("xss", "sql", "browserhijacking", "commandinjection", "uploading", "http_flood")):
        return "web"
    if "dictionarybruteforce" in label or "bruteforce" in label:
        return "bruteforce"
    if "dns_spoof" in label or "mitm" in label or "arp" in label or "spoof" in label:
        return "spoofing"
    if "mirai" in label or "backdoor" in label or "malware" in label:
        return "mirai"
    return label or "unknown"


def load_attack_taxonomy_map(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    frame = pd.read_csv(path)
    if "event_type" not in frame.columns or "family_key" not in frame.columns:
        return {}
    normalized = frame["event_type"].astype(str).map(_normalize_event_label)
    family_key = frame["family_key"].astype(str).str.strip().str.lower()
    return dict(zip(normalized, family_key))


def _apply_cve_map(
    frame: pd.DataFrame,
    cve_map_path: Path | None,
    *,
    allow_event_type_only: bool = True,
) -> pd.DataFrame:
    if cve_map_path is None or not cve_map_path.exists():
        return frame
    cve_map = pd.read_csv(cve_map_path).copy()
    if cve_map.empty:
        return frame
    if "event_type" in cve_map.columns:
        event_series = cve_map["event_type"].astype("string").str.strip().replace({"": pd.NA})
        cve_map["event_type"] = event_series.map(lambda value: _normalize_event_label(value) if pd.notna(value) else pd.NA)
    if "asset_id" in cve_map.columns:
        cve_map["asset_id"] = cve_map["asset_id"].astype("string").str.strip().replace({"": pd.NA})
    if "timestamp" in cve_map.columns:
        cve_map["timestamp"] = pd.to_datetime(cve_map["timestamp"], errors="coerce")
    value_columns = [column for column in cve_map.columns if column not in {"event_type", "asset_id", "timestamp"}]
    if not value_columns:
        return frame
    merged = frame.copy()
    merged["event_type"] = merged["event_type"].astype(str).map(_normalize_event_label)
    if "cvss_source" not in merged.columns:
        merged["cvss_source"] = pd.NA
    available_key_columns = [column for column in ("event_type", "asset_id", "timestamp") if column in cve_map.columns]
    for key_columns in CVE_MAP_KEY_PRIORITY:
        if key_columns == ("event_type",) and not allow_event_type_only:
            continue
        if not all(column in cve_map.columns for column in key_columns):
            continue
        extra_key_columns = [column for column in available_key_columns if column not in key_columns]
        overlay_columns = [*dict.fromkeys([*key_columns, *extra_key_columns, *value_columns])]
        overlay = cve_map[overlay_columns].copy()
        for extra_column in extra_key_columns:
            overlay = overlay.loc[overlay[extra_column].isna()]
        if overlay.empty:
            continue
        overlay["cvss_source"] = "+".join(key_columns)
        overlay = overlay[[*key_columns, *value_columns, "cvss_source"]]
        if "timestamp" in key_columns:
            overlay = overlay.dropna(subset=["timestamp"])
            if overlay.empty:
                continue
        overlay = overlay.drop_duplicates(subset=list(key_columns), keep="last")
        suffix = "__cve_" + "_".join(key_columns)
        merged = merged.merge(overlay, on=list(key_columns), how="left", suffixes=("", suffix))
        for column in value_columns:
            overlay_column = f"{column}{suffix}"
            if overlay_column not in merged.columns:
                continue
            existing = merged[column] if column in merged.columns else pd.Series(index=merged.index, dtype=merged[overlay_column].dtype)
            merged[column] = merged[overlay_column].combine_first(existing)
            merged = merged.drop(columns=[overlay_column])
        source_column = f"cvss_source{suffix}"
        if source_column in merged.columns:
            merged["cvss_source"] = merged[source_column].combine_first(merged["cvss_source"])
            merged = merged.drop(columns=[source_column])
    return merged


def _apply_hf_overlay(frame: pd.DataFrame, hf_overlay_path: Path | None) -> pd.DataFrame:
    if hf_overlay_path is None or not hf_overlay_path.exists():
        return frame
    overlay = pd.read_csv(hf_overlay_path)
    available_hf_columns = [column for column in HF_COLUMNS if column in overlay.columns]
    if not available_hf_columns:
        return frame
    overlay = overlay.copy()
    if "asset_id" not in overlay.columns:
        raise ValueError("HF overlay must contain at least an 'asset_id' column.")
    overlay["asset_id"] = overlay["asset_id"].astype(str)
    if "timestamp" in overlay.columns:
        overlay["timestamp"] = pd.to_datetime(overlay["timestamp"], errors="coerce")
        overlay = overlay.dropna(subset=["timestamp"])
        if overlay.empty:
            return frame
        merged = frame.merge(
            overlay[["asset_id", "timestamp", *available_hf_columns]].drop_duplicates(subset=["asset_id", "timestamp"], keep="last"),
            on=["asset_id", "timestamp"],
            how="left",
            suffixes=("", "__hf_real"),
        )
    else:
        merged = frame.merge(
            overlay[["asset_id", *available_hf_columns]].drop_duplicates(subset=["asset_id"], keep="last"),
            on="asset_id",
            how="left",
            suffixes=("", "__hf_real"),
        )
    for column in available_hf_columns:
        overlay_column = f"{column}__hf_real"
        if overlay_column in merged.columns:
            merged[column] = pd.to_numeric(merged[overlay_column], errors="coerce").combine_first(
                pd.to_numeric(merged.get(column), errors="coerce")
            )
            merged = merged.drop(columns=[overlay_column])
    real_mask = merged[available_hf_columns].notna().all(axis=1)
    merged["hf_source"] = np.where(real_mask, HF_SOURCE_REAL, merged.get("hf_source", HF_SOURCE_NONE))
    return merged


def _normalize_column_names(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in frame.columns:
        key = column.strip().lower().replace(" ", "_")
        renamed[column] = STANDARD_COLUMN_MAP.get(key, key)
    return frame.rename(columns=renamed)


def _ensure_required_columns(frame: pd.DataFrame, taxonomy_map: dict[str, str] | None = None) -> pd.DataFrame:
    taxonomy_map = taxonomy_map or {}
    if "timestamp" not in frame.columns:
        frame["timestamp"] = pd.date_range("2025-01-01", periods=len(frame), freq="min")
    else:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        missing_timestamps = frame["timestamp"].isna()
        if missing_timestamps.any():
            frame.loc[missing_timestamps, "timestamp"] = pd.date_range(
                "2025-01-01", periods=int(missing_timestamps.sum()), freq="min"
            ).to_numpy()
    if "asset_id" not in frame.columns:
        for candidate in ("src_ip", "source_ip", "device_id", "__source_file", "__source_parent"):
            if candidate in frame.columns:
                frame["asset_id"] = frame[candidate].astype(str)
                frame["asset_id_source"] = candidate
                break
        else:
            frame["asset_id"] = "asset_unknown"
            frame["asset_id_source"] = "fallback_constant"
    else:
        frame["asset_id"] = frame["asset_id"].astype(str)
        if "asset_id_source" not in frame.columns:
            frame["asset_id_source"] = "provided"
    if "label" in frame.columns:
        label_numeric = pd.to_numeric(frame["label"], errors="coerce")
        if label_numeric.notna().all():
            frame["label"] = (label_numeric > 0).astype(int)
        else:
            label_text = frame["label"].map(_normalize_event_label)
            if "event_type" not in frame.columns:
                frame["event_type"] = label_text
            else:
                event_text = frame["event_type"].map(_normalize_event_label)
                weak_event_mask = event_text.isin({"merged_csv", "csv", "unknown", ""})
                frame.loc[weak_event_mask, "event_type"] = label_text[weak_event_mask]
            frame["label"] = label_text.map(lambda value: int(taxonomy_map.get(value, infer_event_family(value)) != "benign"))
    if "event_type" not in frame.columns:
        frame["event_type"] = frame.get("__source_parent", frame.get("__source_file", "unknown")).map(_normalize_event_label)
    else:
        frame["event_type"] = frame["event_type"].map(_normalize_event_label)
    if "label" not in frame.columns:
        frame["label"] = frame["event_type"].map(lambda value: int(taxonomy_map.get(value, infer_event_family(value)) != "benign"))
    return frame


def _attach_asset_value_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    numeric_asset_value = pd.to_numeric(frame.get("asset_value_raw"), errors="coerce") if "asset_value_raw" in frame.columns else None
    if numeric_asset_value is not None and numeric_asset_value.notna().any():
        frame["asset_value_raw"] = numeric_asset_value
        if numeric_asset_value.isna().any():
            asset_median = frame.groupby("asset_id", sort=False)["asset_value_raw"].transform("median")
            frame["asset_value_raw"] = frame["asset_value_raw"].fillna(asset_median)
        frame["asset_value_raw"] = frame["asset_value_raw"].fillna(frame["asset_value_raw"].median()).fillna(100000.0)
        frame["asset_value_source"] = frame.get("asset_value_source", "provided")
        return frame

    candidate_metrics = [
        ("byte_rate", 0.45),
        ("packet_rate", 0.30),
        ("flow_duration", 0.15),
        ("avg_packet_size", 0.10),
    ]
    available_metrics = [(column, weight) for column, weight in candidate_metrics if column in frame.columns]
    if not available_metrics:
        frame["asset_value_raw"] = 100000.0
        frame["asset_value_source"] = "default_constant"
        return frame

    per_asset = frame.groupby("asset_id", sort=False)[[column for column, _ in available_metrics]].median().reset_index()
    score = np.zeros(len(per_asset), dtype=float)
    total_weight = 0.0
    for column, weight in available_metrics:
        values = np.log1p(pd.to_numeric(per_asset[column], errors="coerce").fillna(0.0).to_numpy(dtype=float))
        lower = float(np.nanmin(values))
        upper = float(np.nanmax(values))
        if np.isclose(lower, upper):
            normalized = np.full_like(values, 0.5, dtype=float)
        else:
            normalized = np.clip((values - lower) / (upper - lower), 0.0, 1.0)
        score += weight * normalized
        total_weight += weight
    per_asset["asset_value_raw"] = 50000.0 + 450000.0 * (score / max(total_weight, 1e-9))
    frame = frame.drop(columns=["asset_value_raw"], errors="ignore").merge(
        per_asset[["asset_id", "asset_value_raw"]],
        on="asset_id",
        how="left",
    )
    frame["asset_value_source"] = "telemetry_proxy"
    return frame


def _attach_default_cve_features(
    frame: pd.DataFrame,
    cve_map_path: Path | None = None,
    nvd_cache_path: Path | None = None,
    nvd_api_key: str | None = None,
    taxonomy_map: dict[str, str] | None = None,
    allow_event_type_surrogates: bool = True,
) -> pd.DataFrame:
    frame = frame.copy()
    taxonomy_map = taxonomy_map or {}
    event_family = frame["event_type"].map(lambda value: taxonomy_map.get(_normalize_event_label(value), infer_event_family(value)))
    frame = _apply_cve_map(frame, cve_map_path, allow_event_type_only=allow_event_type_surrogates)
    if "cvss_source" not in frame.columns:
        frame["cvss_source"] = pd.NA
    if "cve_id" not in frame.columns:
        frame["cve_id"] = pd.Series(index=frame.index, dtype="string")
    neutral_profile = NEUTRAL_CVE_PROFILE
    if allow_event_type_surrogates:
        default_profiles = event_family.map(lambda value: CVE_PROFILES.get(value, CVE_PROFILES["benign"]))
        default_cve_ids = default_profiles.map(lambda profile: profile.cve_id)
        default_source = "event_family_surrogate"
    else:
        default_profiles = pd.Series([neutral_profile] * len(frame), index=frame.index, dtype="object")
        default_cve_ids = pd.Series([neutral_profile.cve_id] * len(frame), index=frame.index, dtype="object")
        default_source = "global_neutral_prior"
    missing_cves = frame["cve_id"].isna()
    if missing_cves.any():
        frame.loc[missing_cves, "cve_id"] = default_cve_ids[missing_cves]
        frame.loc[missing_cves, "cvss_source"] = frame.loc[missing_cves, "cvss_source"].fillna(default_source)
    required_cvss_columns = ["cvss_exploitability", "cvss_c", "cvss_i", "cvss_a"]
    needs_cache = any(column not in frame.columns or frame[column].isna().any() for column in required_cvss_columns)
    if nvd_cache_path and needs_cache:
        cache = enrich_cves_with_cache(frame["cve_id"].dropna().astype(str).tolist(), nvd_cache_path, api_key=nvd_api_key)
    else:
        cache = {}
    for source_column, target_column in [
        ("cvss_exploitability", "exploitability"),
        ("cvss_c", "impact_c"),
        ("cvss_i", "impact_i"),
        ("cvss_a", "impact_a"),
    ]:
        if source_column in frame.columns:
            values = pd.to_numeric(frame[source_column], errors="coerce")
        else:
            values = pd.Series(index=frame.index, dtype="float64")
        if cache:
            cache_key = {
                "cvss_exploitability": "cvss_exploitability",
                "cvss_c": "cvss_c",
                "cvss_i": "cvss_i",
                "cvss_a": "cvss_a",
            }[source_column]
            values = values.fillna(frame["cve_id"].map(lambda value: cache.get(str(value), {}).get(cache_key)))
        default_values = default_profiles.map(lambda profile: getattr(profile, target_column))
        missing_before_fill = values.isna()
        frame[source_column] = values.fillna(default_values).astype(float)
        if missing_before_fill.any():
            frame.loc[missing_before_fill, "cvss_source"] = frame.loc[missing_before_fill, "cvss_source"].fillna(default_source)
    frame["cvss_source"] = frame["cvss_source"].fillna("curated_map")
    return frame


def _fill_missing_numeric_features(frame: pd.DataFrame) -> pd.DataFrame:
    expected_numeric = [
        "asset_value_raw",
        "flow_duration",
        "packet_rate",
        "byte_rate",
        "syn_flag_number",
        "ack_flag_number",
        "rst_flag_number",
        "http",
        "dns",
        "tcp",
        "udp",
        "icmp",
        "failed_logins",
        "port_entropy",
        "device_entropy",
        "unusual_peer_ratio",
        *HF_COLUMNS,
    ]
    for column in expected_numeric:
        if column not in frame.columns:
            if column == "asset_value_raw":
                frame[column] = 100000.0
            else:
                frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    numeric_columns = frame.select_dtypes(include="number").columns
    frame.loc[:, numeric_columns] = frame.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return frame


def load_real_data(profile_cfg: dict) -> pd.DataFrame:
    data_cfg = profile_cfg.get("data", {})
    raw_dir = Path(data_cfg.get("raw_ciciot_dir", "data/raw/ciciot2023"))
    max_input_files = data_cfg.get("max_input_files")
    rows_per_input_file = data_cfg.get("rows_per_input_file")
    max_total_rows = data_cfg.get("max_total_rows")
    sample_fraction = data_cfg.get("sample_fraction")
    sample_random_state = int(data_cfg.get("sample_random_state", 42))
    allow_event_type_cve_map = bool(data_cfg.get("allow_event_type_cve_map", False))
    csv_paths = sorted(raw_dir.rglob("*.csv"))
    input_count = len(csv_paths)
    if not csv_paths:
        merged_zip = raw_dir / "CSV" / "MERGED_CSV.zip"
        csv_zip = raw_dir / "CSV" / "CSV.zip"
        if merged_zip.exists():
            with ZipFile(merged_zip) as archive:
                input_count = sum(
                    1 for member_name in archive.namelist() if not member_name.endswith("/") and member_name.lower().endswith(".csv")
                )
        elif csv_zip.exists():
            with ZipFile(csv_zip) as archive:
                input_count = sum(
                    1 for member_name in archive.namelist() if not member_name.endswith("/") and member_name.lower().endswith(".csv")
                )
    if max_input_files is not None and input_count:
        input_count = min(int(max_input_files), int(input_count))
    if rows_per_input_file is None and max_total_rows is not None and input_count:
        rows_per_input_file = max(1, int(max_total_rows) // int(input_count))
    if csv_paths:
        frame = _read_csv_files(
            csv_paths,
            max_input_files=max_input_files,
            rows_per_input_file=rows_per_input_file,
            sample_fraction=sample_fraction,
            sample_random_state=sample_random_state,
        )
    else:
        merged_zip = raw_dir / "CSV" / "MERGED_CSV.zip"
        csv_zip = raw_dir / "CSV" / "CSV.zip"
        if merged_zip.exists():
            frame = _read_csv_members_from_zip(
                merged_zip,
                max_input_files=max_input_files,
                rows_per_input_file=rows_per_input_file,
                sample_fraction=sample_fraction,
                sample_random_state=sample_random_state,
            )
        elif csv_zip.exists():
            frame = _read_csv_members_from_zip(
                csv_zip,
                max_input_files=max_input_files,
                rows_per_input_file=rows_per_input_file,
                sample_fraction=sample_fraction,
                sample_random_state=sample_random_state,
            )
        else:
            raise FileNotFoundError("No extracted CSV files or official CSV archives were found in data/raw/ciciot2023")
    frame = _normalize_column_names(frame)
    taxonomy_value = data_cfg.get("attack_taxonomy_path", "data/attack_taxonomy.csv")
    taxonomy_path = Path(taxonomy_value) if taxonomy_value else None
    taxonomy_map = load_attack_taxonomy_map(taxonomy_path)
    frame = _ensure_required_columns(frame, taxonomy_map=taxonomy_map)
    frame = _attach_asset_value_proxy(frame)
    hf_overlay_value = data_cfg.get("hf_overlay_path")
    hf_overlay_path = Path(hf_overlay_value) if hf_overlay_value else None
    frame = _apply_hf_overlay(frame, hf_overlay_path)
    hf_columns_present = any(column in frame.columns for column in HF_COLUMNS) and frame[list(HF_COLUMNS)].notna().any(axis=1).any()
    cve_map_value = data_cfg.get("cve_map_path", "data/cve_map.csv")
    cve_map_path = Path(cve_map_value) if cve_map_value else None
    nvd_cache_value = data_cfg.get("nvd_cache_path", "data/nvd_cache.json")
    nvd_cache_path = Path(nvd_cache_value) if nvd_cache_value else None
    nvd_api_key = data_cfg.get("nvd_api_key")
    frame = _attach_default_cve_features(
        frame,
        cve_map_path,
        nvd_cache_path=nvd_cache_path,
        nvd_api_key=nvd_api_key,
        taxonomy_map=taxonomy_map,
        allow_event_type_surrogates=allow_event_type_cve_map,
    )
    frame = _fill_missing_numeric_features(frame)
    if "hf_source" not in frame.columns:
        frame["hf_source"] = HF_SOURCE_REAL if hf_columns_present else HF_SOURCE_NONE
    elif not hf_columns_present:
        frame["hf_source"] = frame["hf_source"].fillna(HF_SOURCE_NONE)
        frame.loc[frame["hf_source"] != HF_SOURCE_REAL, "hf_source"] = HF_SOURCE_NONE
    frame.attrs["load_params"] = {
        "max_input_files": max_input_files,
        "rows_per_input_file": rows_per_input_file,
        "max_total_rows": max_total_rows,
        "sample_fraction": sample_fraction,
        "sample_random_state": sample_random_state,
        "input_count": input_count,
        "hf_overlay_path": str(hf_overlay_path) if hf_overlay_path else "",
        "allow_event_type_cve_map": allow_event_type_cve_map,
    }
    frame = frame.sort_values(["timestamp", "asset_id"]).reset_index(drop=True)
    return frame
