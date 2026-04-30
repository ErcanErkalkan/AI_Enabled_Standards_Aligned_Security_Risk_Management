from __future__ import annotations

import csv

from ai_risk import reference_data
from ai_risk.utils.io import write_rows


def test_build_reference_bundle_uses_cached_nist_catalog_and_removes_stale_tco_artifacts(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    write_rows(
        data_dir / "nist_csf_2_0_subcats.csv",
        [
            {
                "id": "GV.OV-01",
                "title": "Example subcategory",
                "function": "Govern",
                "category": "Oversight",
                "informative_references": "",
                "linked_iso_ids": "A.5.1",
            }
        ],
        ["id", "title", "function", "category", "informative_references", "linked_iso_ids"],
    )
    for stale_name in ("tco_params.csv", "usage_baseline.csv", "usage_nsga2.csv"):
        (data_dir / stale_name).write_text("stale\n", encoding="utf-8")

    def _unexpected_fetch() -> bytes:
        raise AssertionError("fetch_csf_workbook_bytes should not be called when a cached NIST catalog exists.")

    monkeypatch.setattr(reference_data, "fetch_csf_workbook_bytes", _unexpected_fetch)

    paths = reference_data.build_reference_bundle(tmp_path, refresh=False)

    assert paths.nist_catalog.exists()
    assert (data_dir / "mapping_iso_csf_gqm.csv").exists()
    assert (data_dir / "iso_nist_semantic_crosswalk.csv").exists()
    assert not (data_dir / "tco_params.csv").exists()
    assert not (data_dir / "usage_baseline.csv").exists()
    assert not (data_dir / "usage_nsga2.csv").exists()

    mapping_rows = list(csv.DictReader((data_dir / "mapping_iso_csf_gqm.csv").open("r", encoding="utf-8", newline="")))
    iso_row = next(row for row in mapping_rows if row["framework"] == "ISO27001:2022" and row["id"] == "A.5.1")
    assert iso_row["linked_ids"] == "GV.OV-01"
