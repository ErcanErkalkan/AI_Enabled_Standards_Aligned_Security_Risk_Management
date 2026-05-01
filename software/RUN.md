# Run Guide

## Scope of the strict public profile

The strict public profile is a representation-level and telemetry-evidence demonstration. It does not fully activate all AV--EP--IL--HF risk factors. CVSS exploitability is represented by a global neutral prior, asset value is a telemetry-derived proxy, the HF term is inactive, device attribution is based on source-file cohorts, and timestamps are synthesized. Full risk-engine validation requires deployment-specific overlays for asset values, device identities, row-varying CVE/CVSS mappings, observed HF indicators, and measured control effects.

This guide describes how to reproduce the artifact in `ai_risk/`.

## Project identifiers

- Zenodo DOI: <https://doi.org/10.5281/zenodo.19928296>
- GitHub repository: <https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management>
- Author ORCID: <https://orcid.org/0000-0001-9259-7112>

## 1. Set up the environment

```powershell
cd ai_risk
pip install -e .[dev]
```

## 2. Build reference assets and validate mappings

```powershell
python scripts/build_reference_data.py
python scripts/build_ciciot_metadata.py
python tools/validate_mappings.py
```

Notes:

- `build_reference_data.py` is cache-first. If `data/nist_csf_2_0_subcats.csv` already exists, it can rebuild offline.
- Use `python scripts/build_reference_data.py --refresh` to refresh the official NIST workbook input.

Expected validator summary:

```text
ISO Annex A coverage: 93/93 (100.0%)
NIST CSF 2.0 coverage: 106/106 (100.0%)
Broken links (UML/GQM/IDs): 0
Duplicate or dangling rows: 0
Informative-reference crosswalk mismatches (official ISO<->NIST refs): 0
```

## 3. Run the demo profile

```powershell
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
```

Representative outputs:

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

The project does not auto-download CICIoT2023 because the official access flow is form-gated.
Place the required files under:

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

The loader supports local cache usage and API-backed enrichment logic. If `cve_map.csv`
already carries CVSS fields, unnecessary runtime NVD calls are avoided.

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
