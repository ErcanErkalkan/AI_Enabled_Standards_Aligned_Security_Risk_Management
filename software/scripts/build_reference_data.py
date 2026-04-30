from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.reference_data import build_reference_bundle
from ai_risk.validator import validate_reference_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or refresh reference data artifacts.")
    parser.add_argument("--refresh", action="store_true", help="Overwrite existing reference files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_reference_bundle(ROOT, refresh=args.refresh)
    summary = validate_reference_artifacts(ROOT, write_log=True)
    print(f"ISO Annex A coverage: {summary['iso_coverage']}/{summary['iso_total']} ({(summary['iso_coverage'] / summary['iso_total']) * 100:.1f}%)")
    print(f"NIST CSF 2.0 coverage: {summary['nist_coverage']}/{summary['nist_total']} ({(summary['nist_coverage'] / summary['nist_total']) * 100:.1f}%)")
    print(f"Broken links (UML/GQM/IDs): {summary['broken_links']}")
    print(f"Duplicate or dangling rows: {summary['duplicate_or_dangling']}")
    print(f"Informative-reference crosswalk mismatches (official ISO<->NIST refs): {summary['informative_reference_crosswalk_mismatches']}")


if __name__ == "__main__":
    main()
