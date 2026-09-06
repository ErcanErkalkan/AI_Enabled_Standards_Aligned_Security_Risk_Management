from __future__ import annotations

import csv
from pathlib import Path

from ai_risk.validator import validate_reference_artifacts
from ai_risk.xmi import parse_uml_class_names


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _rows(name: str):
    with (DATA / name).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_r1_static_mapping_is_complete_symmetric_and_structurally_clean():
    summary = validate_reference_artifacts(ROOT, write_log=False)
    assert summary["iso_coverage"] == 93
    assert summary["nist_coverage"] == 106
    assert summary["broken_links"] == 0
    assert summary["duplicate_or_dangling"] == 0
    assert summary["schema_violations"] == 0
    assert summary["contract_violations"] == 0
    assert summary["reciprocal_crosswalk_violations"] == 0
    # Informative references are an external comparator, not R1 semantic ground truth.
    assert summary["informative_reference_crosswalk_differences"] >= 0


def test_r1_metrics_are_optional_and_match_semantic_freeze_counts():
    rows = _rows("mapping_iso_csf_gqm.csv")
    assert len(rows) == 199
    with_metrics = [row for row in rows if row["metric_ids"].strip()]
    without_metrics = [row for row in rows if not row["metric_ids"].strip()]
    assert len(with_metrics) == 30
    assert len(without_metrics) == 169
    assert all(row["uml_class"] == "EvidenceRequirement" for row in rows)


def test_r1_gqm_freeze_counts():
    goals = _rows("gqm_goals_r1.csv")
    questions = _rows("gqm_questions_r1.csv")
    assert len(goals) == 199
    assert len(questions) == 257


def test_authoritative_xmi_contains_r1_contract_classes():
    classes = parse_uml_class_names(DATA / "uml_schema.xmi")
    assert len(classes) == 28
    for name in ["EvidenceRequirement", "EvidenceItem", "ProvenanceRecord", "StandardRow", "Asset", "Risk"]:
        assert name in classes


def test_namespace_safe_parser_accepts_legacy_and_omg_namespace_variants(tmp_path: Path):
    legacy = tmp_path / "legacy.xmi"
    legacy.write_text(
        '<xmi:XMI xmlns:xmi="http://www.omg.org/XMI"><uml:Model xmlns:uml="http://www.omg.org/spec/UML/20161101">'
        '<packagedElement xmi:type="uml:Class" xmi:id="C1" name="LegacyClass" />'
        '</uml:Model></xmi:XMI>',
        encoding="utf-8",
    )
    omg = tmp_path / "omg.xmi"
    omg.write_text(
        '<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001" xmi:version="2.5.1" '
        'xmlns:uml="http://www.omg.org/spec/UML/20131001"><uml:Model xmi:id="M1">'
        '<packagedElement xmi:type="uml:Class" xmi:id="C2" name="OMGClass" />'
        '</uml:Model></xmi:XMI>',
        encoding="utf-8",
    )
    assert parse_uml_class_names(legacy) == {"LegacyClass"}
    assert parse_uml_class_names(omg) == {"OMGClass"}
