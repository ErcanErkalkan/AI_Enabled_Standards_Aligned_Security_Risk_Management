# Artifact Status

This workspace now contains the executable `ai_risk` artifact referenced by the manuscript and locally generated outputs for the core validation paths.

## Commands executed locally

```powershell
cd ai_risk
pip install -e .[dev]
python scripts/build_reference_data.py
python tools/validate_mappings.py
python scripts/build_ciciot_metadata.py
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
python scripts/run_demo_study.py --config configs/default.yaml --profile real_smoke
python scripts/run_demo_study.py --config configs/default.yaml --profile real
python -m pytest -q --basetemp .pytest_tmp
```

## Generated outputs

- Validator logs: `ai_risk/out/logs/`
- Demo outputs: `ai_risk/out/demo/`
- Public-data smoke outputs: `ai_risk/out/real_smoke/`
- Resource-aware public-data outputs: `ai_risk/out/real/`

## Key verified results

- Validator coverage: `93/93` ISO Annex A and `106/106` NIST CSF 2.0 with `0` broken links and `0` duplicate/dangling rows
- Validator semantic crosswalk check: `0` mismatches against official NIST informative-reference ISO links
- `real_smoke` artifact-default scorer: `F1=0.995`, `AUROC=0.997`, `Brier=0.006`
- `real` artifact-default scorer: `F1=0.995`, `AUROC=0.997`, `Brier=0.006`
- Test suite: `23 passed`

## Local data wiring

- `ai_risk/data/raw/ciciot2023` is wired to a local CICIoT2023 download already present on this machine.
- Derived metadata were generated into `ai_risk/data/attack_taxonomy.csv`, `ai_risk/data/attack_victims.csv`, `ai_risk/data/cve_map.csv`, and `ai_risk/data/nvd_cache.json`.
