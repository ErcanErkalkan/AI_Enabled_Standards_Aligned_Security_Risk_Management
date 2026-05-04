from __future__ import annotations

from pathlib import Path

from ai_risk.reference_data import build_reference_bundle
from ai_risk.validator import validate_reference_artifacts


def test_reference_data_validator_reports_full_coverage(tmp_path: Path):
    build_reference_bundle(tmp_path)
    summary = validate_reference_artifacts(tmp_path, write_log=False)
    assert summary["iso_coverage"] == 93
    assert summary["nist_coverage"] == 106
    assert summary["broken_links"] == 0
    assert summary["duplicate_or_dangling"] == 0
    assert summary["schema_violations"] == 0
    assert summary["semantic_crosswalk_mismatches"] == 0
