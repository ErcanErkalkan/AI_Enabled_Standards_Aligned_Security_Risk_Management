# Run Guide

## System requirements

- **Python**: >=3.11; locally verified in this workspace with Python 3.14.3
- **Operating system**: Linux, macOS, or Windows (tested locally on Windows)
- **Memory**: Minimum 8 GB RAM; 16 GB recommended for `real_full`
- **Disk**: ~500 MB for installation and generated outputs; ~5 GB for CICIoT2023 raw data if acquired separately
- **Execution time**: `demo` ~ 1-2 minutes; `real_smoke` ~ 3-5 minutes; `real` ~ 15-30 minutes; `real_full` ~ 60+ minutes depending on RAM and CPU

## Scope of the strict public profile

The strict public profile is a representation-level and telemetry-evidence demonstration. It does not fully activate all AV--EP--IL--HF risk factors. CVSS exploitability is represented by a global neutral prior, asset value is a telemetry-derived proxy, the HF term is inactive, device attribution is based on source-file cohorts, and timestamps are synthesized. Full risk-engine validation requires deployment-specific overlays for asset values, device identities, row-varying CVE/CVSS mappings, observed HF indicators, and measured control effects.

This guide describes how to reproduce the artifact from the `software/` package directory. The installed Python package is named `ai_risk`.

## Reproducibility: pinned and lower-bound environments

For maximum reproducibility, use the provided lock file:

```powershell
cd software
pip install -r requirements.lock
pip install -e .[dev]
```

Equivalent command using the frozen file:

```powershell
cd software
pip install -r requirements-frozen.txt
pip install -e .[dev]
```

The `pyproject.toml` intentionally keeps lower-bound constraints for installability on current Python environments. The lock files pin the locally verified direct dependency versions for the reported reproduction run.

Alternatively, create a fresh environment using lower-bound constraints:

```powershell
cd software
pip install -e .[dev]
pip freeze > requirements-current.txt
```

## Project identifiers

- Zenodo DOI: <https://doi.org/10.5281/zenodo.19928296>
- GitHub repository: <https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management>
- Author ORCID: <https://orcid.org/0000-0001-9259-7112>

## 1. Set up the environment

```powershell
cd software
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e .[dev]
```

On Unix-like shells, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## 2. Validator structural integrity and seeded-defect testing

Before running full profiles, validate the core mapping artifacts and test the validator's defect-detection capability:

```powershell
python scripts/build_reference_data.py
python tools/validate_mappings.py
python tools/test_validator_seeded_defects.py
python scripts/build_semantic_review_packet.py --sample-size 60
```

Expected validator summary in a clean state:

```text
ISO Annex A coverage: 93/93 (100.0%)
NIST CSF 2.0 coverage: 106/106 (100.0%)
Broken links (UML/GQM/IDs): 0
Duplicate or dangling rows: 0
Schema violations: 0
Informative-reference crosswalk mismatches (official ISO<->NIST refs): 0
```

Expected seeded-defect test summary:

```text
Seeded-defect injection test
Defect type            | Injected | Detected | Precision | Recall
Broken metric link     |       50 |       50 |      1.00 |   1.00
Duplicate row          |       50 |       50 |      1.00 |   1.00
Dangling linked id     |       50 |       50 |      1.00 |   1.00
Wrong crosswalk        |       50 |       50 |      1.00 |   1.00
Missing metric field   |       50 |       50 |      1.00 |   1.00
Schema violation       |        1 |        1 |      1.00 |   1.00
```

Notes:

- `build_reference_data.py` is cache-first. If `data/nist_csf_2_0_subcats.csv` already exists, it can rebuild offline.
- Use `python scripts/build_reference_data.py --refresh` to refresh the official NIST workbook input.
- `build_semantic_review_packet.py` creates blank reviewer templates under `out/review/`. These templates support future independent human semantic adjudication; they are not completed expert reviews by themselves.
- `test_validator_seeded_defects.py` copies the reference-data directory to temporary workspaces, injects artificial defects, and scores detections from the real validator output.

## 3. Demo execution path

```powershell
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
```

Expected core demo outputs:

- `out/demo/ids_results.csv`
- `out/demo/default_telemetry_scorer_summary.csv`
- `out/demo/rq_summary.csv`
- `out/demo/fixed_fpr_operating_points.csv`
- `out/demo/optimization_baselines.csv`
- `out/demo/optimization_policy_constraints.csv`
- `out/demo/portfolio_weight_sensitivity.csv`
- `out/demo/reliability_curve.png`
- `out/demo/pareto_front.png`

## 4. Public-data execution path

### 4.1 CICIoT2023 inputs

Official dataset overview:

- <https://www.unb.ca/cic/datasets/iotdataset-2023.html>

The project does not auto-download CICIoT2023 because the official access flow is form-gated. Place the required files under:

```text
data/raw/ciciot2023/
  CSV/
    MERGED_CSV.zip
    CSV.zip
  example/
    example.ipynb
  Supplementary Materials/
    README_Victims_List.pdf
```

`python scripts/build_ciciot_metadata.py` generates:

```text
data/attack_taxonomy.csv
data/attack_victims.csv
data/cve_map.csv
data/nvd_cache.json
```

Run it after the official notebook and victims PDF are present:

```powershell
python scripts/build_ciciot_metadata.py
```

Supported curated CVE map formats:

```text
event_type,cve_id,cvss_exploitability,cvss_c,cvss_i,cvss_a
asset_id,event_type,cve_id,cvss_exploitability,cvss_c,cvss_i,cvss_a
asset_id,timestamp,event_type,cve_id,cvss_exploitability,cvss_c,cvss_i,cvss_a
```

More specific rows override more general rows.

Important behavior:

- `real`, `real_smoke`, and `real_full` default to `allow_event_type_cve_map: false`.
- This prevents event-only CVE joins derived from public labels from leaking attack identity into the headline evaluation.
- Curated `asset_id` or `asset_id + timestamp` joins remain supported and are treated as the safe path when available.
- Raw rows are split before windowing.
- If surrogate source-file cohorts are used as assets, split boundaries are aligned to cohort transitions.

Optional HF overlay columns:

```text
asset_id,hf_failure_ratio,hf_policy_violations,hf_training_gap
```

If a `timestamp` column is present, merges can be done on `asset_id + timestamp`.

### 4.2 NVD enrichment

Official NVD reference:

- <https://services.nvd.nist.gov/rest/json/cves/2.0>

The loader supports local cache usage and API-backed enrichment logic. If `cve_map.csv` already carries CVSS fields, unnecessary runtime NVD calls are avoided.

### 4.3 Run public-data profiles

```powershell
python scripts/run_demo_study.py --config configs/default.yaml --profile real_smoke
python scripts/run_demo_study.py --config configs/default.yaml --profile real
python scripts/run_demo_study.py --config configs/default.yaml --profile real_full
```

Notes:

- `real_smoke` is the fast validation path.
- `real` is the resource-aware profile used for the main reported run.
- `real_full` removes the row cap and requires more RAM and runtime.
- `out/*/split_summary.csv` records both raw-row and window-level split summaries.
- `out/*/optimization_baselines.csv` reports frontier-producing NSGA-II, Greedy-prefix, and Exact-ILP comparators on the common ResidualRisk/TCO plane.
- `out/*/optimization_policy_constraints.csv` records optional DR/FPR policy thresholds and whether they are enabled for the reported frontier comparison.
- Public CICIoT2023 rows do not expose victim/device identifiers.
- Public merged CSV members do not expose observed timestamps, so the ordering is still a surrogate chronology.
- If enterprise asset values are unavailable, `asset_value_raw` is derived as a telemetry proxy.
- If no HF overlay is provided, all rows are tagged `HF:none` and HF ablation remains flat.

Profile-specific output directories:

```text
out/demo/
out/real_smoke/
out/real/
out/real_full/
```

## 5. Run tests

```powershell
python -m pytest -q --basetemp .pytest_tmp
```

### Artifact Reviewer Minimal Path

To run the tests offline without making any network calls to external servers (e.g., NIST), use the `--offline` flag:

```powershell
python -m pytest -q --offline --basetemp .pytest_tmp
```

Expected test result after installing the package and development dependencies:

```text
23 passed
```

## 6. Output snapshot manifest

Generated profile outputs are not Git-tracked source files. For submission or archival, create or refresh the checksum manifest before packaging static snapshots:

```powershell
$roots = @('out\real','out\real_smoke')
$lines = foreach ($root in $roots) {
  Get-ChildItem -Path $root -File | Sort-Object FullName | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    $relative = Resolve-Path -LiteralPath $_.FullName -Relative
    "$($hash.Hash)  $relative"
  }
}
Set-Content -LiteralPath 'ARCHIVED_OUTPUTS_MANIFEST.sha256' -Value $lines -Encoding ascii
```

The static output snapshot should be uploaded as journal supplementary material or as an explicit Zenodo file when the submission system requires immutable reported-output files.
