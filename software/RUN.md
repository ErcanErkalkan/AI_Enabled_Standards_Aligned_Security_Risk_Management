# Run Guide

## System requirements

- Python >= 3.11
- Linux, macOS, or Windows
- 8 GB RAM minimum; 16 GB recommended for `real_full`
- Approximately 500 MB for installation and generated outputs; raw CICIoT2023 data require additional space

## Reproducible environment

```bash
cd software
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
python -m pip install -r requirements.lock
python -m pip install -e .[dev]
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

`requirements.lock` is the canonical install file. `requirements-frozen.txt` is an equivalent archival snapshot; `pyproject.toml` keeps lower-bound constraints for installability.

## Canonical integrity and structural validation

```bash
sha256sum -c CANONICAL_SHA256SUMS.txt
python tools/validate_mappings.py
python tools/test_validator_seeded_defects.py
```

Expected clean validator summary:

```text
ISO Annex A coverage: 93/93
NIST CSF 2.0 coverage: 106/106
Broken links: 0
Duplicate/dangling rows or catalog IDs: 0
Schema/XMI violations: 0
Contract violations: 0
Reciprocal crosswalk violations: 0
```

The deterministic structural smoke suite contains 11 scenarios:

1. unknown metric
2. duplicate mapping row
3. dangling link
4. duplicate link token
5. invalid framework
6. blank title
7. duplicate GQM reference
8. title/catalog mismatch
9. rogue mapping row
10. asymmetric crosswalk
11. malformed XMI

Expected final line:

```text
All 11 seeded structural scenarios detected with structured findings.
```

The committed reference mapping is the canonical study artifact. `scripts/build_reference_data.py --refresh` is a maintenance/test-fixture operation and must not be used as a prerequisite to reproduce the canonical study state.

## Demo execution

```bash
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
```

Core outputs include IDS results, fixed-FPR operating points, optimization baselines, reliability curves, and Pareto-front plots under `out/demo/`.

## Public CICIoT2023 execution

Official dataset overview:
<https://www.unb.ca/cic/datasets/iotdataset-2023.html>

Place the acquired dataset under `data/raw/ciciot2023/` and build optional metadata with:

```bash
python scripts/build_ciciot_metadata.py
```

Public-data profiles:

```bash
python scripts/run_demo_study.py --config configs/default.yaml --profile real_smoke
python scripts/run_demo_study.py --config configs/default.yaml --profile real
python scripts/run_demo_study.py --config configs/default.yaml --profile real_full
```

The public case-study profile does not constitute deployment certification. Device attribution, timestamps, enterprise asset values, row-varying CVE/CVSS mappings, human-factor overlays, and measured control effects require deployment-specific data when those inputs are unavailable in the public dataset.

## Test suite

```bash
python -m pytest -q --basetemp .pytest_tmp
```

Expected result:

```text
28 passed
```

The GitHub Actions workflow additionally verifies the canonical SHA-256 manifest, runs the mapping validator, and executes all 11 structural-fault scenarios.

## Semantic assessment boundary

Independent semantic assessment covers a 60-row stratified sample (30 ISO + 30 NIST). Final sample outcomes are 47 acceptable and 13 requiring targeted minor adjustment. First-pass overall agreement is 55/60 with Cohen's kappa 0.762. Six rating disagreements were resolved by consensus without a third rater. A separate pair-level consistency assessment resolved seven reciprocal crosswalk cases.

These sample statistics apply only to the 60 independently assessed rows. The other 139 rows retain study-derived semantic classification and are not described as independently validated.

The neutral supplementary evidence package stores the final semantic mapping, complete GQM catalog, and semantic-assessment results. Blank future assessment templates can be generated separately when needed.

## Output snapshot manifest

Generated profile outputs are not Git-tracked source files. For archival use, generate an explicit SHA-256 manifest for the selected output snapshot before packaging.
