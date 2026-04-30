# Strict Reviewer Assessment for Computer Standards & Interfaces

## Verdict

Major revision, but scope-compatible with `Computer Standards & Interfaces`.

## Why the paper fits CSI

- The journal explicitly targets standards, information management, interfaces, methods, software quality, metrics, and information security.
- This manuscript's strongest contribution is not a new detector alone, but a machine-readable standards-traceability artifact that links UML/XMI entities, GQM mappings, ISO/IEC 27001:2022 controls, NIST CSF 2.0 subcategories, and reporting exports.
- That positioning is materially closer to CSI than to a pure AI-performance journal.

## Major reviewer concerns

1. **Representation novelty is clearer than validation maturity.**  
   The manuscript is persuasive on machine-readable structure, traceability, and validator coverage. It is materially less persuasive on whether the semantic correctness of each evidence-to-control mapping has been independently established by human raters.

2. **The public empirical profile remains surrogate-heavy.**  
   The reported run relies on source-file cohorts, synthesized ordering, no row-level device identifiers, a telemetry proxy for asset value, and a neutral CVSS prior. That is acceptable for an artifact demonstration, but it weakens claims about deployment-grade external validity.

3. **Downstream risk transformation is only partially activated with public data.**  
   In the strict public profile, exploitability does not vary row by row, human-factor terms are inactive, and asset values are not drawn from an enterprise register. A strict CSI reviewer will accept this only if the paper continues to describe the work as a standards-traceable artifact with partial empirical activation, not as a fully validated operational risk engine.

4. **Optimization results should be read as advisory scenario analysis.**  
   NSGA-II, Greedy, and Exact-ILP comparisons are useful for standards-linked reporting, but they do not demonstrate observed intervention effects in a live security program. The current framing in the manuscript is now more careful, and that caution should be preserved in any revision response.

5. **Research-data compliance must stay explicit.**  
   CSI's current guide requires either repository deposition and citation or a clear explanation of why data cannot be shared. The manuscript now states that upstream CICIoT2023 and NVD/CVSS raw inputs are third-party and therefore not redistributed, while derived artifacts are shared.

## Strengths that matter for CSI

- Full machine-readable standards coverage is a strong point: `93/93` ISO controls and `106/106` NIST CSF 2.0 subcategories are validated by script.
- The paper is organized around specification, validation, interoperability, and reporting reuse, which is aligned with the journal's scope.
- The manuscript now includes a separate highlights file and a separate graphical abstract file, matching the current CSI submission format.
- The public run is written more cautiously as an artifact-level benchmark rather than as an overclaimed deployment result.

## Remaining acceptance risks

- Lack of independent semantic adjudication remains the biggest scientific weakness.
- The data-availability path is adequate for submission, but a repository DOI for the shared artifact package would still help.
- The manuscript is still long; tighter prose would improve editorial reception even if the technical substance is retained.

## Files adjusted for CSI

- `elsarticle-template-num.tex`
- `cover.tex`
- `csi-highlights.txt`
- `SUBMISSION_CHECKLIST.md`
- `README.md`
- `figures/graphical_abstract.puml`
- `figures/graphical_abstract.png`
- `figures/graphical_abstract.pdf`
