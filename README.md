# AI-Enabled Standards-Aligned Security Risk Management

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

- **Zenodo DOI:** [10.5281/zenodo.19928296](https://doi.org/10.5281/zenodo.19928296)
- **GitHub repository:** [ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management](https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management)
- **Author ORCID:** [0000-0001-9259-7112](https://orcid.org/0000-0001-9259-7112)

## Zenodo and GitHub Compatibility
This repository is configured for archiving on Zenodo and hosting on GitHub:
- Both `CITATION.cff` and `.zenodo.json` files are provided in the root to ensure proper citation parsing by GitHub and metadata extraction by Zenodo releases.
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
