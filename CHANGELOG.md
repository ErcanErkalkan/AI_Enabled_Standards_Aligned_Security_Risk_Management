# Changelog

All notable changes to this repository will be documented in this file.

## [Unreleased]

### Added

- Promoted the Science of Computer Programming R1 authoritative UML/XMI metamodel to the canonical software tree.
- Added the final 199-row evidence-first semantic mapping, 211 reciprocal ISO–NIST pairs, 199 GQM goals, and 257 GQM questions.
- Added namespace-safe XMI parsing, the extended structural validator, reciprocal-crosswalk validation, seeded structural regression, and an exact-byte SHA-256 manifest for the canonical R1 files.
- Added GitHub Actions clean regression for exact-byte verification, the complete pytest suite, canonical mapping validation, and seeded defect testing.

### Changed

- Replaced the pre-R1 15-class public UML schema with the validated R1 28-class model.
- Replaced forced generic metric bundles with the post-adjudication evidence-first metric bindings.
- Updated the canonical ISO/IEC 27001:2022 and NIST CSF 2.0 mappings after independent semantic review, human adjudication, reciprocal-consistency resolution, and the Step 12L freeze.
- Clarified that NIST informative-reference differences are an external comparator rather than semantic validation errors.
- Prepared release metadata for the next public software version, planned as v0.2.0; the historical v0.1.0 Zenodo DOI remains provenance for the earlier archive only.

### Validation

- Exact tested canonical code commit: `0962f1b19951da793a90169682e746b70471eeaf`.
- Clean GitHub Actions regression: 28 tests passed; ISO coverage 93/93; NIST coverage 106/106; 0 broken links, duplicate/dangling rows, schema/XMI violations, contract violations, or reciprocal-crosswalk violations; 11/11 seeded structural defect scenarios detected.

## [0.1.0] - 2026-04-11

### Added

- GitHub-ready repository structure with root documentation and licensing
- Citation and Zenodo archive metadata
- Root ignore rules for raw datasets, generated outputs, Python caches, and LaTeX build artefacts
- Public `software/` artifact layout with local-only `paper/` manuscript materials withheld until publication

### Changed

- Professionalized repository and package documentation in English
- Updated package metadata for public repository use
