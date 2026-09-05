# AI-Enabled Standards-Aligned Security Risk Management

**Description:** A Model-Based Software Engineering Framework for Standards-Traceable Security Evidence Management in IoT-Enabled Systems. This artifact encodes security requirements, controls, telemetry observations, and standard clauses into a machine-readable UML/XMI representation and provides an automated validator for structural integrity.

**Topics (Tags):** `mbse`, `cybersecurity`, `traceability`, `uml`, `xmi`, `iso-27001`, `nist-csf`, `evidence-management`

**Release Notes:**
- Version 0.1.0: Initial public reproducible software archive linked to Zenodo DOI 10.5281/zenodo.19928296.
- The Science of Computer Programming R1 revision introduces candidate metamodel, validator, semantic-review, and evaluation changes that are being validated separately. Those R1-specific changes are not represented by the v0.1.0 Zenodo archive and will not be promoted to the public software release until the revision validation gates are complete.

This public repository contains the executable `ai_risk` software artifact and metadata for the standards-aligned security risk management study. Manuscript materials are kept locally under `paper/` and are intentionally not published to GitHub until the paper is published.

## Workspace layout

```text
.
+-- software/                    # Python package, configs, scripts, tests, reference data
+-- CITATION.cff                 # Citation metadata
+-- .zenodo.json                 # Zenodo metadata for archiving
+-- LICENSE                      # Licensing information
`-- README.md                    # This file
```

## Packages

### Software (Data and Code)
Contains the executable artifact `ai_risk`, evaluation pipelines, test suite, and machine-readable standards mapping.
- **Location:** `software/`
- **Main files:** `software/pyproject.toml`, `software/README.md`

### Manuscript Materials
The local workspace may contain a `paper/` directory with manuscript sources, figures, and submission files. That directory is ignored by Git and is not part of the public GitHub repository until publication.

## Persistent Identifiers

- **Zenodo DOI (public v0.1.0 archive):** [10.5281/zenodo.19928296](https://doi.org/10.5281/zenodo.19928296)
- **GitHub repository:** [ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management](https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management)
- **Author ORCID:** [0000-0001-9259-7112](https://orcid.org/0000-0001-9259-7112)

## Zenodo and GitHub Compatibility
This repository is configured for archiving on Zenodo and hosting on GitHub:
- Both `CITATION.cff` and `.zenodo.json` files are provided in the root to ensure proper citation parsing by GitHub and metadata extraction by Zenodo releases.
- The current public Zenodo record is version 0.1.0. It is a historical public archive and must not be interpreted as containing later R1-specific revision artifacts unless a new version is explicitly published.
- The repository metadata points to the Zenodo DOI, GitHub repository, and author ORCID listed above.
- The public GitHub repository currently exposes the software artifact and machine-readable metadata; manuscript files remain local until publication.

## Quick start (Software)

To run the codebase and validate the artifacts:

```powershell
cd software
pip install -r requirements.lock
pip install -e .[dev]
python tools/validate_mappings.py
python tools/test_validator_seeded_defects.py
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
python -m pytest -q --basetemp .pytest_tmp
```

For the full execution guide, see [software/RUN.md](software/RUN.md).

## Artifact Submission Notes

When exporting plots and diagrams as EPS or PDF files for journal submission, ensure that Type 3 fonts are not used, as they are often rejected by preflight systems (like Elsevier's Editorial Manager). 

If using Matplotlib to generate figures, enforce Type 1 or TrueType fonts by adding the following to your script:
```python
import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
```
