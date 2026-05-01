# AI-Enabled Standards-Aligned Security Risk Management

This workspace bundles the manuscript source and the executable `ai_risk` software artifact used by the paper, separated into two main packages to align with best practices for reproducibility.

## Workspace layout

```text
.
+-- paper/                       # Manuscript files, figures, cover letter, and reviews
+-- software/                    # Python package, configs, scripts, tests, reference data
+-- CITATION.cff                 # Citation metadata
+-- .zenodo.json                 # Zenodo metadata for archiving
+-- LICENSE                      # Licensing information
`-- README.md                    # This file
```

## Packages

### 1. Paper (Manuscript)
Contains the LaTeX source code, compiled PDFs, bibliography, figures, and submission-related checklists for the manuscript.
- **Location:** `paper/`
- **Main files:** `elsarticle-template-num.tex`, `elsarticle-template-num.pdf`

### 2. Software (Data and Code)
Contains the executable artifact `ai_risk`, evaluation pipelines, test suite, and machine-readable standards mapping.
- **Location:** `software/`
- **Main files:** `software/pyproject.toml`, `software/README.md`

## Persistent Identifiers

- **Zenodo DOI:** [10.5281/zenodo.19928296](https://doi.org/10.5281/zenodo.19928296)
- **GitHub repository:** [ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management](https://github.com/ErcanErkalkan/AI_Enabled_Standards_Aligned_Security_Risk_Management)
- **Author ORCID:** [0000-0001-9259-7112](https://orcid.org/0000-0001-9259-7112)

## Zenodo and GitHub Compatibility
This repository is configured for archiving on Zenodo and hosting on GitHub:
- Both `CITATION.cff` and `.zenodo.json` files are provided in the root to ensure proper citation parsing by GitHub and metadata extraction by Zenodo releases.
- The repository metadata points to the Zenodo DOI, GitHub repository, and author ORCID listed above.
- The dual-package structure (`paper` and `software`) provides clear boundaries for readers, reviewers, and automated archiving tools.

## Quick start (Software)

To run the codebase and validate the artifacts:

```powershell
cd software
pip install -e .[dev]
python tools/validate_mappings.py
python scripts/run_demo_study.py --config configs/default.yaml --profile demo
python -m pytest -q --basetemp .pytest_tmp
```

For the full execution guide, see [software/RUN.md](software/RUN.md).
