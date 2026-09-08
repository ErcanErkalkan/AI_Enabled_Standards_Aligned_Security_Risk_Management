# AI-Enabled Standards-Aligned Security Risk Management

A model-based software engineering framework for standards-traceable security evidence management. The artifact binds ISO/IEC 27001:2022 and NIST CSF 2.0 requirements to evidence, GQM intent, UML/XMI structures, telemetry-derived measurements where applicable, and auditable validation outputs.

## Scope

The repository contains the executable `ai_risk` package and machine-readable reference artifacts used by the study:

- 93 ISO/IEC 27001:2022 Annex A controls;
- 106 NIST CSF 2.0 subcategories;
- 199 standards rows and 211 reciprocal ISO–NIST pairs;
- 199 GQM references in the canonical mapping; the full 257-question GQM catalog is distributed with the supplementary evidence package;
- a 28-class UML/XMI model;
- a structural validator and deterministic seeded-fault checks.

The NIST informative-reference set is treated as an external comparator rather than semantic ground truth.

## Validation snapshot

The published v0.2.0 software tree remains the immutable historical release. Its GitHub Actions clean regression reported `28 passed` and the v0.2.0 archive remains available under the DOI below.

The unreleased v0.2.1 correction candidate has now completed automated and external-tool validation on the correction branch. At the pinned corrected commit `0d29aaf98bbb3e4d0532e708642a0df67045e563`:

- `31 passed` in the pytest suite;
- ISO coverage: `93/93`;
- NIST coverage: `106/106`;
- broken links: `0`;
- duplicate/dangling rows or catalog IDs: `0`;
- schema/XMI violations: `0`;
- contract violations: `0`;
- reciprocal crosswalk violations: `0`;
- seeded structural defect scenarios: `11/11` detected with structured findings;
- canonical interoperability-oracle self-check: PASS;
- exact-byte canonical SHA-256 verification: PASS;
- corrected canonical XMI SHA-256: `d1da069ab8b5ed543f4118679d01fa9c78c50de8d67debdb3c8c6dd365e01fac`.

Corrected-XMI GUI round trips were also completed in Papyrus Desktop 2025-06 and Enterprise Architect 17.2.1721. Both preserve the corrected mapping-critical multiplicities, `MappingStatus`, GUI sentinel, and tested structural inventory under documented serializer normalization. Papyrus preserves all seven UML/OCL constraints. Enterprise Architect preserves 0/7 constraints, which remains an explicit tool-specific portability limitation. Raw strict-oracle failures are retained rather than relabeled; see [`software/docs/INTEROP_RESULT_v0.2.1.md`](software/docs/INTEROP_RESULT_v0.2.1.md).

The v0.2.1 correction is still unreleased. Release metadata, final package checksums, tag/release assets, and the new archive DOI must be finalized before this candidate replaces the published v0.2.0 snapshot.

## Repository layout

```text
.
├── software/                    # Python package, tests, reference data and validation tools
├── CITATION.cff                 # Citation metadata
├── .zenodo.json                 # Archive metadata
├── LICENSE
└── README.md
```

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

See [`software/RUN.md`](software/RUN.md) for the full execution guide.

## Persistent identifiers

- GitHub repository: <https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management>
- Author ORCID: <https://orcid.org/0000-0001-9259-7112>
- Published v0.2.0 archive DOI: <https://doi.org/10.5281/zenodo.22643003>
