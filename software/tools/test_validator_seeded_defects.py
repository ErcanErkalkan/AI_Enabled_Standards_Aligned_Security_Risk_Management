#!/usr/bin/env python3
"""Run deterministic seeded-defect checks against the mapping validator.

Each scenario copies the reference-data directory into a temporary workspace,
injects one defect class, runs the real validator, and scores whether the
affected identifiers are reported in the expected validator channel.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.validator import validate_reference_artifacts


COUNT = 50
MAPPING_COLUMNS = ["framework", "id", "title", "metric_ids", "uml_class", "gqm_ref", "linked_ids"]


@dataclass(frozen=True)
class ScenarioResult:
    defect_type: str
    injected: int
    detected: int
    precision: float
    recall: float


def _copy_data_root() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp_dir = tempfile.TemporaryDirectory()
    temp_root = Path(temp_dir.name)
    shutil.copytree(ROOT / "data", temp_root / "data")
    return temp_dir, temp_root


def _load_mapping(root: Path) -> pd.DataFrame:
    return pd.read_csv(root / "data" / "mapping_iso_csf_gqm.csv", dtype=str).fillna("")


def _write_mapping(root: Path, frame: pd.DataFrame) -> None:
    columns = [column for column in MAPPING_COLUMNS if column in frame.columns]
    frame.to_csv(root / "data" / "mapping_iso_csf_gqm.csv", columns=columns, index=False)


def _first_indices(frame: pd.DataFrame, count: int = COUNT, *, require_links: bool = False) -> list[int]:
    candidate = frame
    if require_links:
        candidate = candidate.loc[candidate["linked_ids"].str.strip() != ""]
    return list(candidate.head(count).index)


def _all_target_ids(root: Path, framework: str, current: set[str]) -> list[str]:
    if framework == "ISO27001:2022":
        catalog = pd.read_csv(root / "data" / "nist_csf_2_0_subcats.csv", dtype=str).fillna("")
    else:
        catalog = pd.read_csv(root / "data" / "iso27001_2022_annexA.csv", dtype=str).fillna("")
    return [candidate for candidate in catalog["id"].tolist() if candidate not in current]


def _ids_from_details(details: list[str], marker: str | None = None) -> set[str]:
    detected: set[str] = set()
    for detail in details:
        if marker is not None and marker not in detail:
            continue
        if detail.startswith("Duplicate mapping row:"):
            detected.add(detail.rsplit("::", 1)[-1])
        elif detail.startswith("mapping_iso_csf_gqm.csv:"):
            detected.add("mapping_schema")
        else:
            detected.add(detail.split(":", 1)[0])
    return detected


def _score(defect_type: str, expected_ids: set[str], detected_ids: set[str]) -> ScenarioResult:
    true_positives = len(expected_ids & detected_ids)
    false_positives = len(detected_ids - expected_ids)
    precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 0.0
    recall = true_positives / len(expected_ids) if expected_ids else 0.0
    return ScenarioResult(defect_type, len(expected_ids), true_positives, precision, recall)


def _run_scenario(
    defect_type: str,
    inject: Callable[[Path], set[str]],
    detail_key: str,
    marker: str | None = None,
) -> ScenarioResult:
    temp_dir, temp_root = _copy_data_root()
    try:
        expected_ids = inject(temp_root)
        summary = validate_reference_artifacts(temp_root, write_log=False)
        detected_ids = _ids_from_details(summary[detail_key], marker=marker)
    finally:
        temp_dir.cleanup()
    return _score(defect_type, expected_ids, detected_ids)


def _inject_broken_metric(root: Path) -> set[str]:
    frame = _load_mapping(root)
    indices = _first_indices(frame)
    for offset, index in enumerate(indices, start=1):
        frame.loc[index, "metric_ids"] = f"{frame.loc[index, 'metric_ids']};SEEDED_MISSING_METRIC_{offset:03d}"
    _write_mapping(root, frame)
    return set(frame.loc[indices, "id"])


def _inject_duplicate_rows(root: Path) -> set[str]:
    frame = _load_mapping(root)
    indices = _first_indices(frame)
    duplicated = frame.loc[indices].copy()
    frame = pd.concat([frame, duplicated], ignore_index=True)
    _write_mapping(root, frame)
    return set(duplicated["id"])


def _inject_dangling_link(root: Path) -> set[str]:
    frame = _load_mapping(root)
    indices = _first_indices(frame, require_links=True)
    for offset, index in enumerate(indices, start=1):
        seeded_id = f"SEEDED_DANGLING_LINK_{offset:03d}"
        frame.loc[index, "linked_ids"] = f"{frame.loc[index, 'linked_ids']};{seeded_id}"
    _write_mapping(root, frame)
    return set(frame.loc[indices, "id"])


def _inject_wrong_crosswalk(root: Path) -> set[str]:
    frame = _load_mapping(root)
    indices = _first_indices(frame, require_links=True)
    for index in indices:
        current = set(part.strip() for part in frame.loc[index, "linked_ids"].split(";") if part.strip())
        replacement = _all_target_ids(root, frame.loc[index, "framework"], current)[0]
        frame.loc[index, "linked_ids"] = replacement
    _write_mapping(root, frame)
    return set(frame.loc[indices, "id"])


def _inject_missing_metric_field(root: Path) -> set[str]:
    frame = _load_mapping(root)
    indices = _first_indices(frame)
    frame.loc[indices, "metric_ids"] = ""
    _write_mapping(root, frame)
    return set(frame.loc[indices, "id"])


def _inject_schema_violation(root: Path) -> set[str]:
    frame = _load_mapping(root).drop(columns=["metric_ids"])
    _write_mapping(root, frame)
    return {"mapping_schema"}


def _assert_clean_baseline() -> None:
    summary = validate_reference_artifacts(ROOT, write_log=False)
    failing_keys = [
        "broken_links",
        "duplicate_or_dangling",
        "schema_violations",
        "informative_reference_crosswalk_mismatches",
    ]
    failures = {key: summary[key] for key in failing_keys if summary[key] != 0}
    if failures:
        raise SystemExit(f"Clean mapping baseline has validator findings: {failures}")


def run_seeded_defect_test() -> list[ScenarioResult]:
    _assert_clean_baseline()
    scenarios = [
        ("Broken metric link", _inject_broken_metric, "broken_link_details", "missing metrics"),
        ("Duplicate row", _inject_duplicate_rows, "duplicate_or_dangling_details", "Duplicate mapping row"),
        ("Dangling linked id", _inject_dangling_link, "broken_link_details", "dangling linked ids"),
        ("Wrong crosswalk", _inject_wrong_crosswalk, "semantic_crosswalk_mismatch_details", None),
        ("Missing metric field", _inject_missing_metric_field, "broken_link_details", "empty metric_ids"),
        ("Schema violation", _inject_schema_violation, "schema_violation_details", None),
    ]
    return [_run_scenario(*scenario) for scenario in scenarios]


def main() -> None:
    results = run_seeded_defect_test()

    print("Seeded-defect injection test")
    print(f"{'Defect type':<22} | {'Injected':>8} | {'Detected':>8} | {'Precision':>9} | {'Recall':>6}")
    print("-" * 70)
    for result in results:
        print(
            f"{result.defect_type:<22} | {result.injected:>8} | {result.detected:>8} | "
            f"{result.precision:>9.2f} | {result.recall:>6.2f}"
        )

    failed = [result for result in results if result.recall < 1.0 or result.precision < 1.0]
    if failed:
        raise SystemExit("One or more seeded-defect scenarios were not fully detected.")


if __name__ == "__main__":
    main()
