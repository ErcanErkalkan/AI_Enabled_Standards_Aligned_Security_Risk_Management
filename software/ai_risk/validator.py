from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter
import re
import xml.etree.ElementTree as ET

import pandas as pd

from ai_risk.reference_data import flatten_metric_ids
from ai_risk.utils.io import write_text
from ai_risk.xmi import inspect_xmi


REQUIRED_COLUMNS = {
    "iso27001_2022_annexA.csv": {"id", "title", "domain"},
    "nist_csf_2_0_subcats.csv": {"id", "title", "function", "category", "informative_references", "linked_iso_ids"},
    "metric_catalog.csv": {"metric_id", "description"},
    "mapping_iso_csf_gqm.csv": {"framework", "id", "title", "metric_ids", "uml_class", "gqm_ref", "linked_ids"},
}
VALID_FRAMEWORKS = {"ISO27001:2022", "NIST-CSF-2.0"}


def _split_tokens(raw_value: object) -> list[str]:
    if raw_value is None or pd.isna(raw_value):
        return []
    return [part.strip() for part in str(raw_value).split(";") if part.strip()]


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", "" if value is None or pd.isna(value) else str(value)).strip().casefold()


def _missing_columns(frame: pd.DataFrame, file_name: str) -> list[str]:
    return sorted(REQUIRED_COLUMNS[file_name] - set(frame.columns))


def _duplicate_ids(frame: pd.DataFrame, file_name: str, column: str = "id") -> list[str]:
    if column not in frame.columns:
        return []
    values = frame[column].fillna("").astype(str).str.strip()
    duplicated = values.ne("") & values.duplicated(keep=False)
    return [f"{file_name}: duplicate {column} {value}" for value in sorted(set(values[duplicated]))]


def _official_reference_maps(nist_df: pd.DataFrame, iso_ids: set[str]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    nist_to_iso: dict[str, set[str]] = {}
    if {"id", "linked_iso_ids"}.issubset(nist_df.columns):
        for _, row in nist_df.iterrows():
            nist_to_iso[str(row["id"])] = set(_split_tokens(row.get("linked_iso_ids", "")))
    iso_to_nist: dict[str, set[str]] = {iso_id: set() for iso_id in iso_ids}
    for nist_id, links in nist_to_iso.items():
        for iso_id in links:
            iso_to_nist.setdefault(iso_id, set()).add(nist_id)
    return nist_to_iso, iso_to_nist


def validate_reference_artifacts(root: str | Path, write_log: bool = True) -> dict[str, object]:
    """Validate the structural contract of the published R1 reference artifacts.

    The human-adjudicated R1 crosswalk is not required to equal NIST informative
    references.  Official-reference differences are reported as a comparator,
    while reciprocal consistency, source-catalog membership, GQM uniqueness,
    UML anchors, metric IDs, titles, duplicate tokens, and XMI parseability are
    structural validation criteria.

    Empty ``metric_ids`` are valid in R1: quantitative metrics are optional when
    no direct measurement role exists for a standards row.
    """
    started = perf_counter()
    root = Path(root)
    data_dir = root / "data"
    out_dir = root / "out" / "logs"

    frames: dict[str, pd.DataFrame] = {}
    schema_violations: list[str] = []
    for file_name in REQUIRED_COLUMNS:
        path = data_dir / file_name
        try:
            frames[file_name] = pd.read_csv(path, dtype=str).fillna("")
        except Exception as exc:  # structured file/schema failure rather than an uncaught crash
            frames[file_name] = pd.DataFrame()
            schema_violations.append(f"{file_name}: unable to read ({type(exc).__name__}: {exc})")

    iso_df = frames["iso27001_2022_annexA.csv"]
    nist_df = frames["nist_csf_2_0_subcats.csv"]
    metric_df = frames["metric_catalog.csv"]
    mapping_df = frames["mapping_iso_csf_gqm.csv"]

    for file_name, frame in frames.items():
        if frame.empty and not (data_dir / file_name).exists():
            continue
        missing = _missing_columns(frame, file_name)
        if missing:
            schema_violations.append(f"{file_name}: missing required columns {','.join(missing)}")

    xmi_errors: list[str] = []
    uml_class_names: set[str] = set()
    try:
        inspection = inspect_xmi(data_dir / "uml_schema.xmi")
        uml_class_names = set(inspection.class_names)
        if inspection.root_local_name != "XMI":
            xmi_errors.append(f"uml_schema.xmi: unexpected root element {inspection.root_local_name or '(empty)'}")
        if not uml_class_names:
            xmi_errors.append("uml_schema.xmi: no UML classes detected")
    except (ET.ParseError, OSError, ValueError) as exc:
        xmi_errors.append(f"uml_schema.xmi: parse failure ({type(exc).__name__}: {exc})")
    schema_violations.extend(xmi_errors)

    catalog_violations: list[str] = []
    catalog_violations.extend(_duplicate_ids(iso_df, "iso27001_2022_annexA.csv"))
    catalog_violations.extend(_duplicate_ids(nist_df, "nist_csf_2_0_subcats.csv"))
    catalog_violations.extend(_duplicate_ids(metric_df, "metric_catalog.csv", "metric_id"))

    iso_ids = set(iso_df.get("id", pd.Series(dtype=str)).astype(str))
    nist_ids = set(nist_df.get("id", pd.Series(dtype=str)).astype(str))
    metric_ids = set(metric_df.get("metric_id", pd.Series(dtype=str)).astype(str))
    all_known_ids = iso_ids | nist_ids
    title_lookup: dict[tuple[str, str], str] = {}
    if {"id", "title"}.issubset(iso_df.columns):
        title_lookup.update({("ISO27001:2022", str(r["id"])): str(r["title"]) for _, r in iso_df.iterrows()})
    if {"id", "title"}.issubset(nist_df.columns):
        title_lookup.update({("NIST-CSF-2.0", str(r["id"])): str(r["title"]) for _, r in nist_df.iterrows()})

    broken_links: list[str] = []
    duplicate_or_dangling: list[str] = list(catalog_violations)
    contract_violations: list[str] = []
    reciprocal_violations: list[str] = []
    informative_reference_differences: list[str] = []

    required_mapping_cols = REQUIRED_COLUMNS["mapping_iso_csf_gqm.csv"]
    mapping_ready = required_mapping_cols.issubset(mapping_df.columns)
    if mapping_ready:
        duplicate_rows = mapping_df.duplicated(subset=["framework", "id"], keep=False)
        for _, row in mapping_df.loc[duplicate_rows].iterrows():
            duplicate_or_dangling.append(f"Duplicate mapping row: {row['framework']}::{row['id']}")

        nonblank_gqm = mapping_df["gqm_ref"].astype(str).str.strip().ne("")
        duplicated_gqm = mapping_df.loc[nonblank_gqm, "gqm_ref"].duplicated(keep=False)
        for value in sorted(set(mapping_df.loc[nonblank_gqm].loc[duplicated_gqm, "gqm_ref"].astype(str))):
            duplicate_or_dangling.append(f"Duplicate GQM reference: {value}")

        row_lookup: dict[tuple[str, str], set[str]] = {}
        for _, row in mapping_df.iterrows():
            framework = str(row["framework"]).strip()
            row_id = str(row["id"]).strip()
            row_title = str(row["title"]).strip()
            gqm_ref = str(row["gqm_ref"]).strip()
            uml_class = str(row["uml_class"]).strip()

            if framework not in VALID_FRAMEWORKS:
                contract_violations.append(f"{row_id or '(missing id)'}: invalid framework {framework or '(blank)'}")
                continue
            if not row_id:
                contract_violations.append("(missing id): blank mapping id")
                continue
            if not row_title:
                contract_violations.append(f"{row_id}: blank mapping title")
            if not gqm_ref:
                contract_violations.append(f"{row_id}: empty GQM reference")

            expected_catalog = iso_ids if framework == "ISO27001:2022" else nist_ids
            opposite_catalog = nist_ids if framework == "ISO27001:2022" else iso_ids
            if row_id not in expected_catalog:
                duplicate_or_dangling.append(f"Rogue mapping row: {framework}::{row_id}")
            expected_title = title_lookup.get((framework, row_id))
            if expected_title is not None and _normalize_text(row_title) != _normalize_text(expected_title):
                contract_violations.append(f"{row_id}: normalized title/catalog mismatch")

            row_metric_ids = flatten_metric_ids(str(row["metric_ids"])) if str(row["metric_ids"]).strip() else []
            if len(row_metric_ids) != len(set(row_metric_ids)):
                contract_violations.append(f"{row_id}: duplicate metric token")
            missing_metrics = sorted({value for value in row_metric_ids if value not in metric_ids})
            if missing_metrics:
                broken_links.append(f"{row_id}: missing metrics {','.join(missing_metrics)}")

            if not uml_class:
                broken_links.append(f"{row_id}: empty UML class")
            elif uml_class not in uml_class_names:
                broken_links.append(f"{row_id}: unknown UML class {uml_class}")

            linked_ids = _split_tokens(row["linked_ids"])
            if len(linked_ids) != len(set(linked_ids)):
                contract_violations.append(f"{row_id}: duplicate link token")
            missing_linked = sorted({value for value in linked_ids if value not in all_known_ids})
            if missing_linked:
                broken_links.append(f"{row_id}: dangling linked ids {','.join(missing_linked)}")
            wrong_side = sorted({value for value in linked_ids if value in all_known_ids and value not in opposite_catalog})
            if wrong_side:
                contract_violations.append(f"{row_id}: same-framework linked ids {','.join(wrong_side)}")
            row_lookup[(framework, row_id)] = set(linked_ids)

        iso_mapping_ids = {row_id for framework, row_id in row_lookup if framework == "ISO27001:2022"}
        nist_mapping_ids = {row_id for framework, row_id in row_lookup if framework == "NIST-CSF-2.0"}
        iso_missing = sorted(iso_ids - iso_mapping_ids)
        nist_missing = sorted(nist_ids - nist_mapping_ids)
        if iso_missing:
            duplicate_or_dangling.append(f"Missing ISO rows: {','.join(iso_missing)}")
        if nist_missing:
            duplicate_or_dangling.append(f"Missing NIST rows: {','.join(nist_missing)}")

        for (framework, row_id), links in row_lookup.items():
            target_framework = "NIST-CSF-2.0" if framework == "ISO27001:2022" else "ISO27001:2022"
            for linked_id in sorted(links):
                if linked_id not in all_known_ids:
                    continue
                reciprocal = row_lookup.get((target_framework, linked_id))
                if reciprocal is None or row_id not in reciprocal:
                    reciprocal_violations.append(f"{row_id}<->{linked_id}: missing reciprocal link")

        official_nist_to_iso, official_iso_to_nist = _official_reference_maps(nist_df, iso_ids)
        for (framework, row_id), found in row_lookup.items():
            expected = official_iso_to_nist.get(row_id, set()) if framework == "ISO27001:2022" else official_nist_to_iso.get(row_id, set())
            if found != expected:
                informative_reference_differences.append(
                    f"{row_id}: informative-reference set {','.join(sorted(expected)) or '(none)'}; "
                    f"R1 set {','.join(sorted(found)) or '(none)'}"
                )
    else:
        iso_mapping_ids, nist_mapping_ids = set(), set()

    summary: dict[str, object] = {
        "iso_coverage": len(iso_mapping_ids),
        "iso_total": len(iso_ids),
        "nist_coverage": len(nist_mapping_ids),
        "nist_total": len(nist_ids),
        "broken_links": len(set(broken_links)),
        "duplicate_or_dangling": len(set(duplicate_or_dangling)),
        "schema_violations": len(set(schema_violations)),
        "contract_violations": len(set(contract_violations)),
        "reciprocal_crosswalk_violations": len(set(reciprocal_violations)),
        # Backward-compatible comparator keys. These are not semantic errors in R1.
        "informative_reference_crosswalk_mismatches": len(informative_reference_differences),
        "semantic_crosswalk_mismatches": len(informative_reference_differences),
        "informative_reference_crosswalk_differences": len(informative_reference_differences),
        "broken_link_details": sorted(set(broken_links)),
        "duplicate_or_dangling_details": sorted(set(duplicate_or_dangling)),
        "schema_violation_details": sorted(set(schema_violations)),
        "contract_violation_details": sorted(set(contract_violations)),
        "reciprocal_crosswalk_details": sorted(set(reciprocal_violations)),
        "semantic_crosswalk_mismatch_details": sorted(informative_reference_differences),
        "informative_reference_crosswalk_difference_details": sorted(informative_reference_differences),
        "elapsed_seconds": perf_counter() - started,
    }

    if write_log:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        lines = [
            f"ISO Annex A coverage: {summary['iso_coverage']}/{summary['iso_total']}",
            f"NIST CSF 2.0 coverage: {summary['nist_coverage']}/{summary['nist_total']}",
            f"Broken links: {summary['broken_links']}",
            f"Duplicate/dangling rows or catalog IDs: {summary['duplicate_or_dangling']}",
            f"Schema/XMI violations: {summary['schema_violations']}",
            f"Contract violations: {summary['contract_violations']}",
            f"Reciprocal crosswalk violations: {summary['reciprocal_crosswalk_violations']}",
            f"NIST informative-reference differences (comparator, not error): {summary['informative_reference_crosswalk_differences']}",
            f"Elapsed: {summary['elapsed_seconds']:.3f} s",
        ]
        sections = [
            ("Schema/XMI violations", summary["schema_violation_details"]),
            ("Broken links", summary["broken_link_details"]),
            ("Duplicate/dangling", summary["duplicate_or_dangling_details"]),
            ("Contract violations", summary["contract_violation_details"]),
            ("Reciprocal crosswalk violations", summary["reciprocal_crosswalk_details"]),
            ("Informative-reference differences", summary["informative_reference_crosswalk_difference_details"]),
        ]
        for title, details in sections:
            if details:
                lines.extend(["", f"[{title}]", *details])
        log_path = out_dir / f"validate_{timestamp}.txt"
        write_text(log_path, "\n".join(lines) + "\n")
        summary["log_path"] = log_path
    return summary
