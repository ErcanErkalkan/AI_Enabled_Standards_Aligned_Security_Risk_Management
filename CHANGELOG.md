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
- Added a reproducible Papyrus/Enterprise Architect rerun protocol and structural preservation oracle for the corrected XMI.
- Added `software/docs/INTEROP_RESULT_v0.2.1.md` to retain the corrected external-tool result and its claim boundary.

### Validation
- 31 pytest tests pass on the correction branch.
- ISO coverage: 93/93.
- NIST coverage: 106/106.
- Broken links, duplicate/dangling rows, schema/XMI violations, contract violations, and reciprocal-crosswalk violations: 0.
- Seeded structural scenarios: 11/11 detected.
- Canonical interoperability oracle self-check: PASS on the corrected XMI inventory (2 packages, 4 primitive types, 7 enumerations, 28 classes, 79 attributes, 27 associations/54 ends, 6 generalizations, 7 constraints).
- Corrected canonical XMI SHA-256: `d1da069ab8b5ed543f4118679d01fa9c78c50de8d67debdb3c8c6dd365e01fac`.
- Canonical exact-byte SHA-256 verification passes for all manifest entries.
- Papyrus Desktop 2025-06 corrected-XMI round trip: raw strict oracle FAIL only because the serializer omits explicit `value="0"` on the four retained `uml:LiteralInteger` lower-value nodes; UML-default-aware diagnostic PASS; full structural inventory, `MappingStatus`, GUI sentinel, corrected multiplicities, and 7/7 constraints preserved.
- Enterprise Architect 17.2.1721 corrected-XMI round trip: raw strict oracle FAIL because EA adds two wrapper/package elements and preserves 0/7 UML/OCL constraints; wrapper-normalized structural diagnostic PASS; both canonical packages, full structural inventory, `MappingStatus`, GUI sentinel, and all four corrected multiplicities preserved.
- Read-only audit of the frozen EA `.qea` repository finds zero rows in the relevant constraint tables and no canonical C01-C07 constraint identifiers, supporting an import/repository constraint-portability limitation rather than an export-only formatting effect.
- Frozen external interoperability evidence ZIP SHA-256: `8b46c4e450aad73ac782a22fc5f5eac860720ab3edade464b9bca37457b882f9`.
- External interoperability does not support a lossless/general UML/OCL claim; the tested claim is structural portability under documented serializer normalization.

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
- Broken links, duplicate/dangling rows or catalog IDs: 0.
- Schema/XMI violations: 0.
- Contract violations: 0.
- Reciprocal crosswalk violations: 0.
- Seeded structural scenarios: 11/11 detected.

## [0.1.0] - 2026-04-11

### Added
- Initial public repository structure, software package, licensing, citation metadata, and reproducibility documentation.
