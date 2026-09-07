# Changelog

All notable public changes to this repository are documented here.

## [Unreleased]

### Fixed
- Corrected the authoritative UML/XMI optionality contract so standards rows, GQM questions, and evidence requirements are not forced to reference quantitative metrics.
- Changed `StandardToMetric.metrics` to `0..*`, `QuestionToMetric.metrics` to `0..*`, `MetricToEvidenceRequirement.metrics` to `0..*`, and `StandardToMeasurementConcept.measurementConcept` to `0..1`.
- Aligned `MappingStatus` with the active semantic-assessment vocabulary: `notAssessed`, `acceptable`, `minorAdjustment`, `majorAdjustment`, `rejected`, and `deferred`.
- Replaced revision/submission-history wording in the authoritative XMI comment with a standalone technical contract description.
- Extended XMI inspection and validation to enforce canonical association multiplicities and enumeration literals.

### Changed
- Canonical regression now runs on pull requests targeting `main` in addition to pushes on `main`.
- Canonical XMI contract regression tests now lock the corrected metric optionality and semantic-status vocabulary.

### Validation
- 31 pytest tests pass on the correction branch.
- ISO coverage: 93/93.
- NIST coverage: 106/106.
- Broken links, duplicate/dangling rows, schema/XMI violations, contract violations, and reciprocal-crosswalk violations: 0.
- Seeded structural scenarios: 11/11 detected.
- Canonical exact-byte SHA-256 verification passes for all manifest entries.
- Corrected external-tool Papyrus/Enterprise Architect round-trip evidence remains pending before v0.2.1 release freeze.

## [0.2.0] - 2026-09-07

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
- Public documentation describes the canonical study artifact and its reproducibility boundary.

### Validation
- 28 pytest tests pass.
- ISO coverage: 93/93.
- NIST coverage: 106/106.
- Broken links, duplicate/dangling rows, schema/XMI violations, contract violations, and reciprocal-crosswalk violations: 0.
- Seeded structural scenarios: 11/11 detected.

## [0.1.0] - 2026-04-11

### Added
- Initial public repository structure, software package, licensing, citation metadata, and reproducibility documentation.
