# UML/XMI interoperability rerun protocol - v0.2.1 correction line

## Purpose

This protocol re-tests the corrected v0.2.1 UML/XMI bytes after the metric-optionality and `MappingStatus` contract corrections. It does **not** treat the published v0.2.0 Papyrus/Enterprise Architect result as evidence for the corrected file. The rerun is an import -> GUI edit -> export experiment, followed by an automated preservation oracle.

## Canonical input and gate

Use `software/data/uml_schema.xmi` from branch `v0.2.1-contract-correction` after the branch CI is green. Record the exact Git commit and SHA-256 of the input file before opening either UML tool. Do not update the manuscript interoperability scope to v0.2.1 until both tool runs, raw exports, screenshots/tool metadata, and oracle reports have been archived.

Expected canonical inventory before the GUI sentinel edit:

- 2 UML packages
- 4 primitive types
- 7 enumerations
- 28 classes
- 79 attributes
- 27 associations / 54 association ends
- 6 generalizations
- 7 UML/OCL constraints

Mapping-critical v0.2.1 contracts:

- `StandardToMetric.metrics = 0..*`
- `QuestionToMetric.metrics = 0..*`
- `MetricToEvidenceRequirement.metrics = 0..*`
- `StandardToMeasurementConcept.measurementConcept = 0..1`
- `MappingStatus = {notAssessed, acceptable, minorAdjustment, majorAdjustment, rejected, deferred}`

## Common evidence to record for each tool

Create a dedicated output directory per tool and retain:

1. exact canonical input XMI and SHA-256;
2. tool name, exact version/build, OS, and export dialect/options;
3. screenshot after import showing the model/package tree;
4. one GUI-created test-only **class** named `RoundTripSentinel_v021`;
5. screenshot showing the sentinel in the model editor/tree;
6. raw exported XMI, without hand editing;
7. SHA-256 of the raw export;
8. strict oracle JSON/text output;
9. any secondary diagnostic oracle output; and
10. a short result note distinguishing structural preservation, constraint preservation/loss, and metadata/serialization rewriting.

The sentinel is test-only and must not be merged into the canonical XMI. Because it is a class, an export checked with `--sentinel RoundTripSentinel_v021` is expected to contain 29 classes (the canonical 28 plus the sentinel) while all other canonical inventory counts remain unchanged.

## Papyrus rerun

Use the same installed Papyrus line as the prior experiment if available (previously Papyrus Desktop 2025-06 / Eclipse 4.36); record the exact current build rather than assuming it is unchanged.

1. Import/open the corrected canonical XMI as a UML model.
2. Confirm that both `TraceabilityCore` and `SecurityContext` are visible.
3. Confirm that the four corrected multiplicities and the six `MappingStatus` literals are visible where the UI exposes them.
4. Create the `RoundTripSentinel_v021` **class** through the GUI.
5. Save/export through the normal UML/XMI path.
6. Run the strict oracle:

```bash
python software/tools/check_interop_export.py \
  papyrus_v021_export.xmi \
  --expected-constraints 7 \
  --sentinel RoundTripSentinel_v021 \
  --json-out papyrus_v021_oracle.json
```

A strict PASS requires the canonical inventory plus the single sentinel class, all seven constraints, the four corrected association ends, `MappingStatus`, and the GUI sentinel to survive. Namespace/version metadata or internal XMI IDs may be rewritten by the tool; byte identity is not required.

## Enterprise Architect rerun

Use the same installed EA line as the prior experiment if available (previously Enterprise Architect 17.2.1721, 64-bit); record the exact current version/build.

1. Create a blank test repository/project.
2. Import the corrected canonical XMI through the UML 2.5.1 / XMI 2.5.1 import path.
3. Confirm that both normative packages are present.
4. Inspect the four corrected multiplicities and `MappingStatus` where the UI exposes them.
5. Create the `RoundTripSentinel_v021` **class** through the GUI.
6. Export the imported model/package through the UML 2.5.1 / XMI 2.5.1 publishing path.
7. Run the same strict oracle with `--expected-constraints 7` and the sentinel argument.

If the prior 7/7 constraint-loss behavior recurs, keep the strict result as **FAIL**; do not relabel it as a strict PASS. A second command may then be run with `--expected-constraints 0` only to characterize whether the remaining structural inventory and corrected mapping-critical contracts survived despite the constraint loss. Archive both reports. This separates a tool-specific constraint-portability boundary from loss of the corrected v0.2.1 mapping contract.

## Acceptance rule for manuscript synchronization

The corrected v0.2.1 manuscript may state tested structural portability only after:

- Papyrus strict report is archived;
- EA strict report is archived, including any constraint-loss result;
- both raw exports contain the GUI sentinel class;
- the four corrected multiplicities and `MappingStatus` survive both exports;
- any tool-specific constraint loss is reported explicitly rather than normalized away; and
- the exact input commit, XMI SHA-256, exports, oracle JSON files, and screenshots are included in the evidence package.

Until then, interoperability statements in the working manuscript must remain scoped to the published v0.2.0 XMI snapshot.
