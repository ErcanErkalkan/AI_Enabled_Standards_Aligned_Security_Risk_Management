# Corrected v0.2.1 UML/XMI interoperability result

## Pinned input

- commit: `0d29aaf98bbb3e4d0532e708642a0df67045e563`
- canonical XMI SHA-256: `d1da069ab8b5ed543f4118679d01fa9c78c50de8d67debdb3c8c6dd365e01fac`
- preservation oracle SHA-256: `8ec0900d0b22c67b1484a261d8be7149f69a08112ba5e17069093c2bf1f88e37`
- frozen external evidence ZIP SHA-256: `8b46c4e450aad73ac782a22fc5f5eac860720ab3edade464b9bca37457b882f9`

The external-tool experiment used the corrected XMI from the pinned commit. In each GUI, a test-only UML class named `RoundTripSentinel_v021` was created before export. Raw strict-oracle failures are retained as failures; secondary diagnostics are reported separately and are not used to rewrite the raw result.

## Papyrus

Tool line: Papyrus Desktop 2025-06 / Eclipse 4.36, build `2025-11-14T15:46:01Z`.

Raw export preserves:

- 2 packages;
- 4 primitive types;
- 7 enumerations;
- 29 classes (28 canonical + `RoundTripSentinel_v021`);
- 79 attributes;
- 27 associations / 54 association ends;
- 6 generalizations;
- 7 UML/OCL constraints;
- the six-literal `MappingStatus` vocabulary; and
- the GUI-created sentinel.

The raw strict oracle is **FAIL** because Papyrus retains the four corrected `uml:LiteralInteger` lower-value nodes but omits their explicit `value="0"` attributes. The strict oracle therefore reads the four lower bounds as `1`. A separate UML-default-aware diagnostic preserves the raw FAIL and returns **PASS** for the semantic multiplicities:

- `StandardToMetric.metrics = 0..*`
- `QuestionToMetric.metrics = 0..*`
- `MetricToEvidenceRequirement.metrics = 0..*`
- `StandardToMeasurementConcept.measurementConcept = 0..1`

## Enterprise Architect

Tool line: Sparx Systems Enterprise Architect 17.2.1721, build 1721, 64-bit.

The full UML 2.5.1/XMI export preserves:

- both canonical packages, `TraceabilityCore` and `SecurityContext`;
- 4 primitive types;
- 7 enumerations;
- 29 classes (28 canonical + `RoundTripSentinel_v021`);
- 79 attributes;
- 27 associations / 54 association ends;
- 6 generalizations;
- all four corrected multiplicities;
- the exact six-literal `MappingStatus` vocabulary; and
- the GUI-created sentinel.

The raw export contains four package elements because EA serializes the two canonical packages together with `StandardsTraceableSecurityEvidenceModel` and `EA_PrimitiveTypes_Package` wrapper/package elements. It preserves 0/7 UML/OCL constraints. The raw strict oracle is therefore **FAIL**. A wrapper-normalized structural diagnostic is **PASS** while retaining the 7/7 constraint loss as an explicit limitation.

A read-only audit of the frozen `.qea` repository finds zero rows in `t_objectconstraint`, `t_attributeconstraints`, `t_connectorconstraint`, and `t_roleconstraint`, and no canonical C01-C07 constraint identifiers in repository text fields. This supports localization of the observed constraint loss to EA import/repository materialization rather than only to export formatting.

## Claim boundary

Supported:

> Tested structural portability of the corrected v0.2.1 mapping-critical UML/XMI contract across the tested Papyrus and Enterprise Architect versions under documented serializer normalization.

Not supported:

- byte-identical cross-tool serialization;
- lossless or general UML/OCL interoperability; or
- generalization to untested UML tools or versions.

Enterprise Architect's loss of all seven UML/OCL constraints remains an explicit tool-specific portability limitation.
