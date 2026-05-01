# ai_risk

`ai_risk` is the Python artifact package for the public software artifact. It
packages the data pipeline, evaluation logic, reporting utilities, and
validation assets required to reproduce the reported software workflows.

## Scope

The package includes:

- ISO/IEC 27001:2022 Annex A and NIST CSF 2.0 traceability assets
- UML/XMI data model and automated mapping validator
- bidirectional ISO<->NIST informative-reference crosswalk checks against official NIST references
- semantic review packet templates and dual-rater scoring utilities for future independent mapping adjudication
- auditable `AV x EP x IL` risk scoring with optional human-factor terms
- boundary-safe preprocessing with raw-row splitting before windowing
- telemetry-only IDS evaluation that keeps CVSS, asset-value, and HF fields out of the classifier
- calibration metrics, reliability curves, Brier score, and fixed-FPR reporting
- NSGA-II, Greedy, and exact epsilon-constraint ILP optimization baselines
- provenance reporting for CVSS, asset value, and HF sources

## Profiles

Four execution profiles are provided:

1. `demo`: synthetic, fast end-to-end sanity-check profile
2. `real_smoke`: lightweight public-data validation profile
3. `real`: resource-aware public-data profile used for the main reported run
4. `real_full`: unrestricted heavier profile for larger machines

## Quick start

```powershell
cd software
pip install -e .[dev]
python scripts/build_reference_data.py
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
python tools/validate_mappings.py
python -m pytest -q --basetemp .pytest_tmp
```

Outputs are written to profile-specific directories under `out/`.

## Persistent identifiers

- Zenodo DOI: [10.5281/zenodo.19928296](https://doi.org/10.5281/zenodo.19928296)
- GitHub repository: [ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management](https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management)
- Author ORCID: [0000-0001-9259-7112](https://orcid.org/0000-0001-9259-7112)

## Public-data constraints

The strict public CICIoT2023 path is intentionally conservative:

- `allow_event_type_cve_map: false` is used for the public headline profiles
- public CSV rows do not expose victim/device identifiers, so source-file cohorts are used as surrogate assets
- public merged CSV members do not carry observed timestamps, so ordering remains a surrogate chronology
- enterprise asset values are unavailable, so telemetry-proxy asset valuation is used
- if no HF overlay is supplied, rows are tagged as `HF:none`

## Documentation

- Run guide: [RUN.md](RUN.md)
- Root repository overview: [../README.md](../README.md)
