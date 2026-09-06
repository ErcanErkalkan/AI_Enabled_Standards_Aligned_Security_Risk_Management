#!/usr/bin/env python3
"""Deterministic structural-defect smoke test for the promoted R1 validator."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable
import xml.etree.ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.validator import validate_reference_artifacts


MAPPING_COLUMNS = ["framework", "id", "title", "metric_ids", "uml_class", "gqm_ref", "linked_ids"]


def _copy_data_root() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp_dir = tempfile.TemporaryDirectory()
    temp_root = Path(temp_dir.name)
    shutil.copytree(ROOT / "data", temp_root / "data")
    return temp_dir, temp_root


def _load_mapping(root: Path) -> pd.DataFrame:
    return pd.read_csv(root / "data" / "mapping_iso_csf_gqm.csv", dtype=str).fillna("")


def _write_mapping(root: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(root / "data" / "mapping_iso_csf_gqm.csv", columns=MAPPING_COLUMNS, index=False)


def _first_linked_index(frame: pd.DataFrame) -> int:
    return int(frame.loc[frame["linked_ids"].str.strip().ne("")].index[0])


def _inject_unknown_metric(root: Path) -> None:
    f = _load_mapping(root); f.loc[0, "metric_ids"] = "SEEDED_UNKNOWN_METRIC"; _write_mapping(root, f)


def _inject_duplicate_mapping(root: Path) -> None:
    f = _load_mapping(root); f = pd.concat([f, f.iloc[[0]]], ignore_index=True); _write_mapping(root, f)


def _inject_dangling_link(root: Path) -> None:
    f = _load_mapping(root); i = _first_linked_index(f); f.loc[i, "linked_ids"] += ";SEEDED_UNKNOWN_ID"; _write_mapping(root, f)


def _inject_duplicate_link_token(root: Path) -> None:
    f = _load_mapping(root); i = _first_linked_index(f); token = f.loc[i, "linked_ids"].split(";")[0]; f.loc[i, "linked_ids"] += f";{token}"; _write_mapping(root, f)


def _inject_invalid_framework(root: Path) -> None:
    f = _load_mapping(root); f.loc[0, "framework"] = "INVALID"; _write_mapping(root, f)


def _inject_blank_title(root: Path) -> None:
    f = _load_mapping(root); f.loc[0, "title"] = ""; _write_mapping(root, f)


def _inject_duplicate_gqm(root: Path) -> None:
    f = _load_mapping(root); f.loc[1, "gqm_ref"] = f.loc[0, "gqm_ref"]; _write_mapping(root, f)


def _inject_title_mismatch(root: Path) -> None:
    f = _load_mapping(root); f.loc[0, "title"] = "SEEDED WRONG TITLE"; _write_mapping(root, f)


def _inject_rogue_row(root: Path) -> None:
    f = _load_mapping(root); rogue = f.iloc[[0]].copy(); rogue.loc[:, "id"] = "A.9.99"; rogue.loc[:, "linked_ids"] = ""; rogue.loc[:, "gqm_ref"] = "GQM-ROGUE-001"; f = pd.concat([f, rogue], ignore_index=True); _write_mapping(root, f)


def _inject_asymmetric_link(root: Path) -> None:
    f = _load_mapping(root); i = _first_linked_index(f); source = f.loc[i, "id"]; target = f.loc[i, "linked_ids"].split(";")[0]; target_index = int(f.index[f["id"].eq(target)][0]); tokens = [x for x in f.loc[target_index, "linked_ids"].split(";") if x and x != source]; f.loc[target_index, "linked_ids"] = ";".join(tokens); _write_mapping(root, f)


def _inject_malformed_xmi(root: Path) -> None:
    (root / "data" / "uml_schema.xmi").write_text("<xmi:XMI><broken>", encoding="utf-8")


SCENARIOS: list[tuple[str, Callable[[Path], None], str]] = [
    ("unknown metric", _inject_unknown_metric, "broken_links"),
    ("duplicate mapping row", _inject_duplicate_mapping, "duplicate_or_dangling"),
    ("dangling link", _inject_dangling_link, "broken_links"),
    ("duplicate link token", _inject_duplicate_link_token, "contract_violations"),
    ("invalid framework", _inject_invalid_framework, "contract_violations"),
    ("blank title", _inject_blank_title, "contract_violations"),
    ("duplicate GQM", _inject_duplicate_gqm, "duplicate_or_dangling"),
    ("title/catalog mismatch", _inject_title_mismatch, "contract_violations"),
    ("rogue mapping row", _inject_rogue_row, "duplicate_or_dangling"),
    ("asymmetric crosswalk", _inject_asymmetric_link, "reciprocal_crosswalk_violations"),
    ("malformed XMI", _inject_malformed_xmi, "schema_violations"),
]


def _assert_clean_baseline() -> None:
    s = validate_reference_artifacts(ROOT, write_log=False)
    fatal = {k: s[k] for k in ["broken_links", "duplicate_or_dangling", "schema_violations", "contract_violations", "reciprocal_crosswalk_violations"] if s[k] != 0}
    if fatal:
        raise SystemExit(f"Clean R1 baseline has validator findings: {fatal}")


def main() -> None:
    _assert_clean_baseline()
    failures: list[str] = []
    for name, inject, key in SCENARIOS:
        td, root = _copy_data_root()
        try:
            inject(root)
            summary = validate_reference_artifacts(root, write_log=False)
            detected = int(summary[key]) > 0
            print(f"{name:<28} {'PASS' if detected else 'FAIL'} ({key}={summary[key]})")
            if not detected:
                failures.append(name)
        except ET.ParseError as exc:
            failures.append(f"{name}: uncaught parse error {exc}")
        finally:
            td.cleanup()
    if failures:
        raise SystemExit("Seeded structural scenarios not detected: " + ", ".join(failures))
    print(f"All {len(SCENARIOS)} seeded structural scenarios detected with structured findings.")


if __name__ == "__main__":
    main()
