# Changelog

All notable public changes to this repository are documented here.

## [Unreleased]

### Added
- Canonical 28-class UML/XMI model.
- Final 199-row standards/evidence mapping with 211 reciprocal ISO–NIST pairs.
- Canonical GQM references in the public mapping; the full 199-goal/257-question catalog is distributed with the supplementary evidence package.
- Namespace-safe XMI parsing, structural validation, reciprocal-crosswalk validation, deterministic seeded-fault checks, and exact-byte SHA-256 verification.
- GitHub Actions regression on `main`.

### Changed
- Reference mappings and validation assets use neutral canonical file names.
- Quantitative metrics are optional when no direct measurement role exists for a standards row.
- NIST informative-reference differences are reported as external-comparator differences rather than semantic validation errors.
- Public documentation describes the study as one canonical artifact rather than as a sequence of internal development states.

### Validation
- 28 pytest tests pass.
- ISO coverage: 93/93.
- NIST coverage: 106/106.
- Broken links, duplicate/dangling rows, schema/XMI violations, contract violations, and reciprocal-crosswalk violations: 0.
- Seeded structural scenarios: 11/11 detected.

## [0.1.0] - 2026-04-11

### Added
- Initial public repository structure, software package, licensing, citation metadata, and reproducibility documentation.
