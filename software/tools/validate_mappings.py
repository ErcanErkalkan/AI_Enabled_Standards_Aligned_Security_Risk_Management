from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.validator import validate_reference_artifacts


def main() -> None:
    summary = validate_reference_artifacts(ROOT, write_log=True)
    print(f"ISO Annex A coverage: {summary['iso_coverage']}/{summary['iso_total']}")
    print(f"NIST CSF 2.0 coverage: {summary['nist_coverage']}/{summary['nist_total']}")
    print(f"Broken links: {summary['broken_links']}")
    print(f"Duplicate/dangling rows or catalog IDs: {summary['duplicate_or_dangling']}")
    print(f"Schema/XMI violations: {summary['schema_violations']}")
    print(f"Contract violations: {summary['contract_violations']}")
    print(f"Reciprocal crosswalk violations: {summary['reciprocal_crosswalk_violations']}")
    print(
        "NIST informative-reference differences (external comparator; not a semantic error): "
        f"{summary['informative_reference_crosswalk_differences']}"
    )
    print(f"Elapsed: {summary['elapsed_seconds']:.3f} s")
    if "log_path" in summary:
        print(f"Log: {summary['log_path']}")

    fatal_keys = [
        "broken_links",
        "duplicate_or_dangling",
        "schema_violations",
        "contract_violations",
        "reciprocal_crosswalk_violations",
    ]
    if any(int(summary[key]) != 0 for key in fatal_keys):
        raise SystemExit("R1 structural validation failed.")


if __name__ == "__main__":
    main()
