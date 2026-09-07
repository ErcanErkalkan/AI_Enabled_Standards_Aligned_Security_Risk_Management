# ai_risk

`ai_risk` is the executable research artifact for standards-traceable security evidence management and the accompanying IoT telemetry case study.

## Included capabilities

- ISO/IEC 27001:2022 Annex A and NIST CSF 2.0 traceability assets
- 28-class UML/XMI model
- reciprocal ISO–NIST crosswalk validation
- GQM references in the canonical standards mapping; the complete GQM catalog is supplied in the supplementary evidence package
- deterministic structural-fault tests
- auditable `AV × EP × IL` risk scoring with optional human-factor terms
- boundary-safe telemetry preprocessing
- telemetry-only IDS evaluation
- calibration and fixed-FPR diagnostics
- NSGA-II, Greedy, and exact epsilon-constraint ILP optimization baselines
- provenance reporting for CVSS, asset value, and human-factor sources

## Canonical reference artifacts

The committed files in `data/` are the study reference state. Ordinary validation reads these files directly and does not regenerate them.

`reference_data.py` and `scripts/build_reference_data.py` provide maintenance/test-fixture reconstruction utilities. They are not prerequisites for reproducing the reported canonical mapping or UML model, and `--refresh` should not be used during ordinary validation.

## Quick start

```bash
cd software
python -m pip install -r requirements.lock
python -m pip install -e .[dev]
sha256sum -c CANONICAL_SHA256SUMS.txt
python tools/validate_mappings.py
python tools/test_validator_seeded_defects.py
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
python -m pytest -q --basetemp .pytest_tmp
```

## Profiles

1. `demo`: synthetic fast end-to-end sanity check
2. `real_smoke`: lightweight public-data validation
3. `real`: resource-aware public-data run
4. `real_full`: unrestricted heavier run

Outputs are written under `out/<profile>/`.

## Public-data constraints

The public CICIoT2023 path is intentionally conservative:

- `allow_event_type_cve_map: false` for headline profiles
- source-file cohorts are used as surrogate assets when device identifiers are unavailable
- ordering is a surrogate chronology when observed timestamps are unavailable
- telemetry proxies are used when enterprise asset values are unavailable
- absent human-factor overlays are recorded as `HF:none`

## Documentation

- Run guide: [`RUN.md`](RUN.md)
- Root overview: [`../README.md`](../README.md)
