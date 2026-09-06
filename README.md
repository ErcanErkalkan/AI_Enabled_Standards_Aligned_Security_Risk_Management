# AI-Enabled Standards-Aligned Security Risk Management

**Description:** A model-based software engineering framework for standards-traceable security evidence management. The artifact binds ISO/IEC 27001:2022 and NIST CSF 2.0 requirements to evidence, GQM intent, UML/XMI structures, telemetry-derived measurements where applicable, and auditable validation outputs.

**Topics (Tags):** `mbse`, `cybersecurity`, `traceability`, `uml`, `xmi`, `iso-27001`, `nist-csf`, `evidence-management`

**Release Notes:**
- **Version 0.1.0:** historical initial public reproducible software archive, preserved at Zenodo DOI `10.5281/zenodo.19928296`.
- **Current main / v0.2.0 candidate:** validated Science of Computer Programming R1 canonical software tree. The authoritative R1 metamodel, evidence-first semantic mapping, GQM catalog, namespace-safe XMI parser, and extended validator have been promoted after the revision validation gates completed.
- Exact tested R1 canonical code commit: `0962f1b19951da793a90169682e746b70471eeaf`.

This public repository contains the executable `ai_risk` software artifact and machine-readable standards/evidence metadata. Manuscript source and submission-only materials remain outside the public repository until publication.

## R1 canonical validation snapshot

The promoted R1 software tree was independently rebuilt in GitHub Actions on Ubuntu 24.04 with CPython 3.13.15. The release-clean regression verified the exact SHA-256 bytes of 16 canonical R1 files and reported:

- `28 passed` in the full pytest suite;
- ISO/IEC 27001:2022 Annex A coverage: `93/93`;
- NIST CSF 2.0 coverage: `106/106`;
- broken links: `0`;
- duplicate/dangling rows or catalog IDs: `0`;
- schema/XMI violations: `0`;
- contract violations: `0`;
- reciprocal crosswalk violations: `0`;
- seeded structural defect scenarios: `11/11` detected with structured findings.

The final R1 semantic artifacts contain 199 standards rows, 211 symmetric ISO–NIST pairs, 199 GQM goals, and 257 GQM questions. NIST informative-reference differences are retained as external-comparator evidence and are not treated as semantic validation errors.

## Workspace layout

```text
.
+-- software/                    # Python package, configs, tests, reference data and R1 canonical SHA manifest
+-- CITATION.cff                 # Citation metadata for the next software version
+-- .zenodo.json                 # Zenodo metadata for GitHub release archiving
+-- LICENSE                      # Licensing information
`-- README.md                    # This file
```

## Packages

### Software (Data and Code)
Contains the executable artifact `ai_risk`, evaluation pipelines, test suite, and machine-readable standards mapping.
- **Location:** `software/`
- **Canonical R1 byte manifest:** `software/R1_CANONICAL_SHA256SUMS.txt`
- **Main files:** `software/pyproject.toml`, `software/README.md`

### Manuscript Materials
The local workspace may contain a `paper/` directory with manuscript sources, figures, reviewer evidence, and submission files. That directory is ignored by Git and is not part of the public repository until publication.

## Persistent Identifiers

- **Historical Zenodo DOI (v0.1.0 only):** [10.5281/zenodo.19928296](https://doi.org/10.5281/zenodo.19928296)
- **Next R1/v0.2.0 Zenodo DOI:** pending creation of the new public release; do not use the v0.1.0 DOI as the identifier for the R1 software snapshot.
- **GitHub repository:** [ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management](https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management)
- **Author ORCID:** [0000-0001-9259-7112](https://orcid.org/0000-0001-9259-7112)

## Zenodo and GitHub compatibility

This repository is configured for Zenodo/GitHub release archiving. `.zenodo.json` is the metadata source used by Zenodo when both `.zenodo.json` and `CITATION.cff` are present. The old v0.1.0 version DOI has therefore been removed from the current `.zenodo.json` so a future R1 release is not incorrectly assigned the historical version DOI.

## Quick start (Software)

```powershell
cd software
pip install -r requirements.lock
pip install -e .[dev]
sha256sum -c R1_CANONICAL_SHA256SUMS.txt
python tools/validate_mappings.py
python tools/test_validator_seeded_defects.py
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
python -m pytest -q --basetemp .pytest_tmp
```

For the full execution guide, see [software/RUN.md](software/RUN.md).

## Artifact Submission Notes

When exporting plots and diagrams as EPS or PDF files for journal submission, ensure that Type 3 fonts are not used. With Matplotlib, for example:

```python
import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
```
