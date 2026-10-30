# R0.18 evidence branch — software and derived data are different versions

**Status:** Research working data snapshot (not a new validated canonical software release). The software baseline `v0.2.1` is immutable and contains 199 rows, 211 undirected ISO–NIST pairs and the canonical 28-class UML/XMI class model. Its frozen study tests historically report **31 passed** (GitHub Actions run `34144576581`; distinct from the R0.18 checks).

The R0.16 **coordinator-ratified derived** CSV in `data/` contains the same 199 row identifiers and **212 undirected pairs (424 reciprocal directed edges)**. Exactly one link was removed (`ID.RA-03`/`A.8.16`), and two links were added (`PR.PS-03`/`A.7.14`, `ID.IM-03`/`A.5.36`). This is **not** a replacement of the original canonical software inputs. The unchanged canonical metamodel SHA-256 is `d1da069ab8b5ed543f4118679d01fa9c78c50de8d67debdb3c8c6dd365e01fac`; a class schema does not contain per-control link instance rows.

The R0.18 follow-up used **15 previously flagged control identities × 2 conditions × 2 raters = 60 rated presentations** (not 60 unique controls): 30 v1, 30 repaired v2. The targeted score means change from 2.9667 to 4.8667 (fidelity), and 3.6667 to 4.7667 (actionability), with 29/30 versus 0/30 flagged overreach. This is targeted **repair re-evaluation**; it does not validate the other 171 new candidate questions or measure real workflow efficiency. The original independently sampled 60 crosswalk rows are a **different unit of analysis** from the 24+4 question-assessment tasks and 15 follow-up repairs.

## How to check from the repository root

```sh
python research/r018/verify_repo_lineage.py
python research/r018/typed/test_typed_repo_smoke.py
```

The optional typed smoke suite tests four local structural cases against `software/data/uml_schema.xmi`. It **does not** reproduce the historical two-tool GUI exports and does **not** change the previously reported 31-test CI figure. The separate archived typed-comparator evidence includes 12 tests and two GUI exports (Papyrus 7/7 OCL constraints, EA 0/7), and must be indexed in the journal's extended evidence package. The historical 55/55 seeded-validator experiment is also a **separate suite**.

## Release provenance

| Object | SHA-256 |
| --- | --- |
| Frozen canonical GitHub mapping `software/data/mapping_iso_csf_gqm.csv` | `3f614840f33cc4be3d3d457ea9deee277486538ee23e3f3e0a594624919bacba` |
| R0.16 ratified derived CSV | `ab431119507295678e3bed3ca8d48269733409302a8def255737160d5a3002ef` |
| Canonical UML/XMI metamodel | `d1da069ab8b5ed543f4118679d01fa9c78c50de8d67debdb3c8c6dd365e01fac` |

The old software release DOI `10.5281/zenodo.22659063` identifies `v0.2.1`, **not a published R0.18 data deposit**. Do not reuse that DOI as proof that this derived research snapshot was deposited.

No general model/OCL semantic equivalence, mapping-instance portability, complete 199-control human semantic validity or superiority over OSCAL/spreadsheets is asserted. The GitHub work branch is an integration candidate; do not cite it as a published release before review/merge and evidence deposit.
