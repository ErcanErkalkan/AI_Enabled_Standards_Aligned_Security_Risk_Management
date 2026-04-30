from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from ai_risk.data_ingest import infer_event_family, load_real_data


def test_infer_event_family_maps_real_ciciot_labels():
    assert infer_event_family("Benign_Final") == "benign"
    assert infer_event_family("DDOS-PSHACK_FLOOD") == "ddos"
    assert infer_event_family("DOS-UDP_FLOOD") == "dos"
    assert infer_event_family("Recon-PortScan") == "recon"
    assert infer_event_family("BrowserHijacking") == "web"
    assert infer_event_family("DictionaryBruteForce") == "bruteforce"
    assert infer_event_family("MITM-ArpSpoofing") == "spoofing"
    assert infer_event_family("Mirai-greip_flood") == "mirai"


def test_load_real_data_reads_official_merged_zip_without_extraction(tmp_path: Path):
    raw_root = tmp_path / "data" / "raw" / "ciciot2023" / "CSV"
    raw_root.mkdir(parents=True)
    data_root = tmp_path / "data"
    archive_path = raw_root / "MERGED_CSV.zip"
    taxonomy_path = data_root / "attack_taxonomy.csv"
    sample = pd.DataFrame(
        [
            {"Rate": 120.0, "Tot sum": 2048.0, "Label": "Benign_Final"},
            {"Rate": 990.0, "Tot sum": 4096.0, "Label": "DDoS-HTTP_Flood"},
        ]
    )
    taxonomy = pd.DataFrame(
        [
            {"event_type": "benign_final", "family_key": "benign"},
            {"event_type": "ddos-http_flood", "family_key": "ddos"},
        ]
    )
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("MERGED_CSV/Merged01.csv", sample.to_csv(index=False))
    taxonomy.to_csv(taxonomy_path, index=False)

    frame = load_real_data(
        {
            "data": {
                "raw_ciciot_dir": str(data_root / "raw" / "ciciot2023"),
                "attack_taxonomy_path": str(taxonomy_path),
                "nvd_cache_path": None,
                "cve_map_path": None,
                "allow_event_type_cve_map": True,
            }
        }
    )

    assert len(frame) == 2
    assert frame.columns.is_unique
    assert frame["label"].tolist() == [0, 1]
    assert frame["event_type"].tolist() == ["benign_final", "ddos-http_flood"]
    assert set(frame["cve_id"]) == {"CVE-0000-0000", "CVE-2024-1101"}
    assert set(frame["hf_source"]) == {"HF:none"}
    assert set(frame["asset_id_source"]) == {"__source_file"}
    assert set(frame["asset_value_source"]) == {"telemetry_proxy"}


def test_load_real_data_respects_source_limits_and_sampling(tmp_path: Path):
    raw_root = tmp_path / "data" / "raw" / "ciciot2023" / "CSV"
    raw_root.mkdir(parents=True)
    data_root = tmp_path / "data"
    archive_path = raw_root / "MERGED_CSV.zip"
    taxonomy_path = data_root / "attack_taxonomy.csv"
    taxonomy = pd.DataFrame(
        [
            {"event_type": "benign_final", "family_key": "benign"},
            {"event_type": "ddos-http_flood", "family_key": "ddos"},
        ]
    )
    with ZipFile(archive_path, "w") as archive:
        for index in range(3):
            sample = pd.DataFrame(
                [
                    {"Rate": float(100 + row), "Tot sum": float(2000 + row), "Label": "Benign_Final" if row % 2 == 0 else "DDoS-HTTP_Flood"}
                    for row in range(10)
                ]
            )
            archive.writestr(f"MERGED_CSV/Merged{index:02d}.csv", sample.to_csv(index=False))
    taxonomy.to_csv(taxonomy_path, index=False)

    frame = load_real_data(
        {
            "data": {
                "raw_ciciot_dir": str(data_root / "raw" / "ciciot2023"),
                "attack_taxonomy_path": str(taxonomy_path),
                "nvd_cache_path": None,
                "cve_map_path": None,
                "max_input_files": 2,
                "rows_per_input_file": 4,
                "sample_fraction": 0.5,
                "sample_random_state": 7,
            }
        }
    )

    assert 0 < len(frame) <= 4
    assert set(frame["asset_id"]) <= {"Merged00.csv", "Merged01.csv"}


def test_load_real_data_derives_rows_per_input_file_from_max_total_rows(tmp_path: Path):
    raw_root = tmp_path / "data" / "raw" / "ciciot2023" / "CSV"
    raw_root.mkdir(parents=True)
    data_root = tmp_path / "data"
    archive_path = raw_root / "MERGED_CSV.zip"
    taxonomy_path = data_root / "attack_taxonomy.csv"
    taxonomy = pd.DataFrame(
        [
            {"event_type": "benign_final", "family_key": "benign"},
            {"event_type": "ddos-http_flood", "family_key": "ddos"},
        ]
    )
    with ZipFile(archive_path, "w") as archive:
        for index in range(4):
            sample = pd.DataFrame(
                [{"Rate": float(100 + row), "Tot sum": float(2000 + row), "Label": "Benign_Final"} for row in range(10)]
            )
            archive.writestr(f"MERGED_CSV/Merged{index:02d}.csv", sample.to_csv(index=False))
    taxonomy.to_csv(taxonomy_path, index=False)

    frame = load_real_data(
        {
            "data": {
                "raw_ciciot_dir": str(data_root / "raw" / "ciciot2023"),
                "attack_taxonomy_path": str(taxonomy_path),
                "nvd_cache_path": None,
                "cve_map_path": None,
                "max_total_rows": 8,
            }
        }
    )

    assert len(frame) == 8
    assert frame.attrs["load_params"]["rows_per_input_file"] == 2


def test_load_real_data_uses_hf_overlay_when_available(tmp_path: Path):
    raw_root = tmp_path / "data" / "raw" / "ciciot2023" / "CSV"
    raw_root.mkdir(parents=True)
    data_root = tmp_path / "data"
    archive_path = raw_root / "MERGED_CSV.zip"
    taxonomy_path = data_root / "attack_taxonomy.csv"
    hf_overlay_path = data_root / "hf_overlay.csv"
    sample = pd.DataFrame(
        [
            {"Rate": 120.0, "Tot sum": 2048.0, "Label": "Benign_Final"},
            {"Rate": 990.0, "Tot sum": 4096.0, "Label": "DDoS-HTTP_Flood"},
        ]
    )
    taxonomy = pd.DataFrame(
        [
            {"event_type": "benign_final", "family_key": "benign"},
            {"event_type": "ddos-http_flood", "family_key": "ddos"},
        ]
    )
    hf_overlay = pd.DataFrame(
        [
            {
                "asset_id": "Merged01.csv",
                "hf_failure_ratio": 0.8,
                "hf_policy_violations": 0.7,
                "hf_training_gap": 0.6,
            }
        ]
    )
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("MERGED_CSV/Merged01.csv", sample.to_csv(index=False))
    taxonomy.to_csv(taxonomy_path, index=False)
    hf_overlay.to_csv(hf_overlay_path, index=False)

    frame = load_real_data(
        {
            "data": {
                "raw_ciciot_dir": str(data_root / "raw" / "ciciot2023"),
                "attack_taxonomy_path": str(taxonomy_path),
                "nvd_cache_path": None,
                "cve_map_path": None,
                "hf_overlay_path": str(hf_overlay_path),
            }
        }
    )

    assert set(frame["hf_source"]) == {"HF:real"}
    assert set(frame["hf_failure_ratio"]) == {0.8}


def test_load_real_data_prefers_asset_level_cve_map_over_event_family_defaults(tmp_path: Path):
    raw_root = tmp_path / "data" / "raw" / "ciciot2023" / "CSV"
    raw_root.mkdir(parents=True)
    data_root = tmp_path / "data"
    archive_path = raw_root / "MERGED_CSV.zip"
    taxonomy_path = data_root / "attack_taxonomy.csv"
    cve_map_path = data_root / "cve_map.csv"
    sample = pd.DataFrame(
        [
            {"Rate": 990.0, "Tot sum": 4096.0, "Label": "DDoS-HTTP_Flood"},
            {"Rate": 995.0, "Tot sum": 4200.0, "Label": "DDoS-HTTP_Flood"},
        ]
    )
    taxonomy = pd.DataFrame(
        [
            {"event_type": "ddos-http_flood", "family_key": "ddos"},
        ]
    )
    cve_map = pd.DataFrame(
        [
            {
                "event_type": "ddos-http_flood",
                "cve_id": "CVE-GENERIC-0001",
                "cvss_exploitability": 0.20,
                "cvss_c": 0.10,
                "cvss_i": 0.10,
                "cvss_a": 0.60,
                "mapping_source": "generic_event_map",
            },
            {
                "asset_id": "Merged01.csv",
                "event_type": "ddos-http_flood",
                "cve_id": "CVE-ASSET-9999",
                "cvss_exploitability": 0.91,
                "cvss_c": 0.72,
                "cvss_i": 0.65,
                "cvss_a": 0.88,
                "mapping_source": "asset_specific_map",
            },
        ]
    )
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("MERGED_CSV/Merged01.csv", sample.to_csv(index=False))
        archive.writestr("MERGED_CSV/Merged02.csv", sample.to_csv(index=False))
    taxonomy.to_csv(taxonomy_path, index=False)
    cve_map.to_csv(cve_map_path, index=False)

    frame = load_real_data(
        {
            "data": {
                "raw_ciciot_dir": str(data_root / "raw" / "ciciot2023"),
                "attack_taxonomy_path": str(taxonomy_path),
                "nvd_cache_path": None,
                "cve_map_path": str(cve_map_path),
                "allow_event_type_cve_map": True,
            }
        }
    )

    asset_specific_rows = frame.loc[frame["asset_id"] == "Merged01.csv"]
    generic_rows = frame.loc[frame["asset_id"] == "Merged02.csv"]

    assert set(asset_specific_rows["cve_id"]) == {"CVE-ASSET-9999"}
    assert set(generic_rows["cve_id"]) == {"CVE-GENERIC-0001"}
    assert set(asset_specific_rows["mapping_source"]) == {"asset_specific_map"}
    assert set(generic_rows["mapping_source"]) == {"generic_event_map"}


def test_load_real_data_defaults_to_neutral_cvss_prior_when_event_only_map_is_disallowed(tmp_path: Path):
    raw_root = tmp_path / "data" / "raw" / "ciciot2023" / "CSV"
    raw_root.mkdir(parents=True)
    data_root = tmp_path / "data"
    archive_path = raw_root / "MERGED_CSV.zip"
    taxonomy_path = data_root / "attack_taxonomy.csv"
    sample = pd.DataFrame(
        [
            {"Rate": 120.0, "Tot sum": 2048.0, "Label": "Benign_Final"},
            {"Rate": 990.0, "Tot sum": 4096.0, "Label": "DDoS-HTTP_Flood"},
        ]
    )
    taxonomy = pd.DataFrame(
        [
            {"event_type": "benign_final", "family_key": "benign"},
            {"event_type": "ddos-http_flood", "family_key": "ddos"},
        ]
    )
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("MERGED_CSV/Merged01.csv", sample.to_csv(index=False))
    taxonomy.to_csv(taxonomy_path, index=False)

    frame = load_real_data(
        {
            "data": {
                "raw_ciciot_dir": str(data_root / "raw" / "ciciot2023"),
                "attack_taxonomy_path": str(taxonomy_path),
                "nvd_cache_path": None,
                "cve_map_path": None,
                "allow_event_type_cve_map": False,
            }
        }
    )

    assert set(frame["cve_id"]) == {"CVE-2024-1103"}
    assert set(frame["cvss_source"]) == {"global_neutral_prior"}
