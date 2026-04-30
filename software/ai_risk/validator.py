from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

from ai_risk.reference_data import flatten_metric_ids, parse_uml_class_names
from ai_risk.utils.io import write_text


def _split_linked_ids(raw_value: object) -> list[str]:
    if pd.isna(raw_value):
        return []
    return [part.strip() for part in str(raw_value).split(";") if part.strip()]


def validate_reference_artifacts(root: str | Path, write_log: bool = True) -> dict[str, object]:
    started = perf_counter()
    root = Path(root)
    data_dir = root / "data"
    out_dir = root / "out" / "logs"
    iso_df = pd.read_csv(data_dir / "iso27001_2022_annexA.csv")
    nist_df = pd.read_csv(data_dir / "nist_csf_2_0_subcats.csv")
    metric_df = pd.read_csv(data_dir / "metric_catalog.csv")
    mapping_df = pd.read_csv(data_dir / "mapping_iso_csf_gqm.csv")
    uml_class_names = parse_uml_class_names(data_dir / "uml_schema.xmi")

    metric_ids = set(metric_df["metric_id"])
    iso_ids = set(iso_df["id"])
    nist_ids = set(nist_df["id"])
    all_known_ids = iso_ids | nist_ids
    official_nist_to_iso = {row["id"]: set(_split_linked_ids(row.get("linked_iso_ids", ""))) for _, row in nist_df.iterrows()}
    official_iso_to_nist: dict[str, set[str]] = {iso_id: set() for iso_id in iso_ids}
    for nist_id, linked_iso_ids in official_nist_to_iso.items():
        for iso_id in linked_iso_ids:
            official_iso_to_nist.setdefault(iso_id, set()).add(nist_id)

    broken_links: list[str] = []
    duplicate_or_dangling: list[str] = []
    semantic_crosswalk_mismatches: list[str] = []

    duplicated = mapping_df.duplicated(subset=["framework", "id"], keep=False)
    for _, row in mapping_df.loc[duplicated].iterrows():
        duplicate_or_dangling.append(f"Duplicate mapping row: {row['framework']}::{row['id']}")

    id_counter = Counter(mapping_df["id"])
    for identifier, count in id_counter.items():
        if count > 1 and identifier in iso_ids and identifier in nist_ids:
            continue

    for _, row in mapping_df.iterrows():
        row_metric_ids = flatten_metric_ids(str(row["metric_ids"]))
        missing_metrics = [metric_id for metric_id in row_metric_ids if metric_id not in metric_ids]
        if missing_metrics:
            broken_links.append(f"{row['id']}: missing metrics {','.join(missing_metrics)}")
        if row["uml_class"] not in uml_class_names:
            broken_links.append(f"{row['id']}: unknown UML class {row['uml_class']}")
        if not str(row["gqm_ref"]).strip():
            broken_links.append(f"{row['id']}: empty GQM reference")
        linked_ids = _split_linked_ids(row.get("linked_ids", ""))
        missing_linked = [linked_id for linked_id in linked_ids if linked_id not in all_known_ids]
        if missing_linked:
            broken_links.append(f"{row['id']}: dangling linked ids {','.join(missing_linked)}")
        if row["framework"] == "NIST-CSF-2.0":
            expected_linked = official_nist_to_iso.get(row["id"], set())
            if set(linked_ids) != expected_linked:
                semantic_crosswalk_mismatches.append(
                    f"{row['id']}: expected ISO links {','.join(sorted(expected_linked)) or '(none)'} "
                    f"but found {','.join(sorted(linked_ids)) or '(none)'}"
                )
        elif row["framework"] == "ISO27001:2022":
            expected_linked = official_iso_to_nist.get(row["id"], set())
            if set(linked_ids) != expected_linked:
                semantic_crosswalk_mismatches.append(
                    f"{row['id']}: expected NIST links {','.join(sorted(expected_linked)) or '(none)'} "
                    f"but found {','.join(sorted(linked_ids)) or '(none)'}"
                )

    iso_mapping_ids = set(mapping_df.loc[mapping_df["framework"] == "ISO27001:2022", "id"])
    nist_mapping_ids = set(mapping_df.loc[mapping_df["framework"] == "NIST-CSF-2.0", "id"])
    iso_missing = sorted(iso_ids - iso_mapping_ids)
    nist_missing = sorted(nist_ids - nist_mapping_ids)
    if iso_missing:
        duplicate_or_dangling.append(f"Missing ISO rows: {','.join(iso_missing)}")
    if nist_missing:
        duplicate_or_dangling.append(f"Missing NIST rows: {','.join(nist_missing)}")

    iso_coverage = len(iso_mapping_ids)
    nist_coverage = len(nist_mapping_ids)
    summary = {
        "iso_coverage": iso_coverage,
        "iso_total": len(iso_ids),
        "nist_coverage": nist_coverage,
        "nist_total": len(nist_ids),
        "broken_links": len(broken_links),
        "duplicate_or_dangling": len(duplicate_or_dangling),
        "informative_reference_crosswalk_mismatches": len(semantic_crosswalk_mismatches),
        "semantic_crosswalk_mismatches": len(semantic_crosswalk_mismatches),
        "elapsed_seconds": perf_counter() - started,
    }

    if write_log:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        lines = [
            f"ISO Annex A coverage: {iso_coverage}/{len(iso_ids)} ({(iso_coverage / len(iso_ids)) * 100:.1f}%)",
            f"NIST CSF 2.0 coverage: {nist_coverage}/{len(nist_ids)} ({(nist_coverage / len(nist_ids)) * 100:.1f}%)",
            f"Broken links (UML/GQM/IDs): {len(broken_links)}",
            f"Duplicate or dangling rows: {len(duplicate_or_dangling)}",
            f"Informative-reference crosswalk mismatches (official ISO<->NIST refs): {len(semantic_crosswalk_mismatches)}",
            f"Elapsed: {summary['elapsed_seconds']:.2f} s",
        ]
        if broken_links:
            lines.append("")
            lines.append("[Broken links]")
            lines.extend(sorted(broken_links))
        if duplicate_or_dangling:
            lines.append("")
            lines.append("[Duplicate or dangling]")
            lines.extend(sorted(duplicate_or_dangling))
        if semantic_crosswalk_mismatches:
            lines.append("")
            lines.append("[Informative-reference crosswalk mismatches]")
            lines.extend(sorted(semantic_crosswalk_mismatches))
        log_path = out_dir / f"validate_{timestamp}.txt"
        write_text(log_path, "\n".join(lines) + "\n")
        summary["log_path"] = log_path
    return summary
