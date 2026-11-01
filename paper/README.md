# Single canonical research project

**Research article:** Control-Scoped Evidence-First GQM for Security Standards Traceability: A Bounded Question-Repair and UML/XMI Evaluation

This directory is the only active, journal-neutral article. The corresponding code lives in the same project repository on the `main` branch under `software/`; previous research source states remain immutable historical evidence, not competing active manuscript versions.

## Contents

- `manuscript.tex` — complete article source in generic LaTeX `article` format (not a publisher template)
- `manuscript.pdf` — compiled complete article, 49 A4 pages
- `cas-refs.bib` and `manuscript.bbl` — source references and fixed compiled bibliography
- `figures/` — figures referenced from the manuscript
- `restored_archival_inputs/` — the two detailed technical tables required by the manuscript
- `SHA256SUMS.txt` — content digests for the included research article sources
- `CANONICAL_STATUS.json` — factual status and scientific boundaries

## Scope

The complete investigation is retained: 199 controls, three distinct mapping states (211/212/192 undirected pairs), the 24-task primary question comparison, the separate 4-task exploratory set, 15 selected repairs, UML/XMI evidence and archived telemetry results. No experiments have been fabricated or retrospectively rerun. Recorded assessor results remain **unverified as to independent identity and institutional authorization**. Real practitioner comparisons, raw-data source verification, and independent field validation are **not claimed**.

The article contains no journal-targeting statements, reviewer-response text, revisions-to-referee declarations or publisher-specific LaTeX class. Prior authoring versions and restricted source evidence remain archived separately for provenance; the discarded 15-page shortened draft is **not** the canonical article.

## Build

Run `pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex` three times from `paper/`. The included `manuscript.bbl` preserves the complete references when a BibTeX executable is unavailable. For a fresh bibliography build, run `bibtex manuscript` once after an initial LaTeX pass, then run `pdflatex` twice.

## Data and redistribution boundaries

The publicly shareable document package does **not** contain original regulated standard texts, private assessor material, missing original 63 CICIoT2023 source CSVs or consent/signature documents. The excluded material cannot be inferred from published aggregates. The package is a research manuscript and associated source; it is not a certified security-standard mapping release or a journal acceptance.
