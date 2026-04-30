from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from ai_risk.reference_data import metric_bundle_for_identifier
from ai_risk.utils.io import ensure_dir, write_frame, write_text


REVIEW_JUDGMENT_COLUMNS = [
    "metric_fit",
    "uml_fit",
    "crosswalk_fit",
    "overall_decision",
]


@dataclass(frozen=True)
class ReviewArtifacts:
    master_packet: Path
    priority_packet: Path
    reviewer_template_a: Path
    reviewer_template_b: Path
    instructions: Path


@dataclass(frozen=True)
class AgreementArtifacts:
    summary_csv: Path
    disagreements_csv: Path
    summary_md: Path


@dataclass(frozen=True)
class ProxyReviewArtifacts:
    reviewer_strict: Path
    reviewer_contextual: Path
    agreement_summary_csv: Path
    agreement_disagreements_csv: Path
    agreement_summary_md: Path
    methods_md: Path


def _split_ids(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def build_semantic_review_packet(root: str | Path) -> pd.DataFrame:
    root = Path(root)
    data_dir = root / "data"
    mapping_df = pd.read_csv(data_dir / "mapping_iso_csf_gqm.csv").fillna("")
    nist_df = pd.read_csv(data_dir / "nist_csf_2_0_subcats.csv").fillna("")
    iso_df = pd.read_csv(data_dir / "iso27001_2022_annexA.csv").fillna("")
    metric_df = pd.read_csv(data_dir / "metric_catalog.csv").fillna("")
    crosswalk_df = pd.read_csv(data_dir / "iso_nist_semantic_crosswalk.csv").fillna("")

    nist_lookup = nist_df.set_index("id").to_dict(orient="index")
    iso_lookup = iso_df.set_index("id").to_dict(orient="index")
    metric_lookup = metric_df.set_index("metric_id")["description"].to_dict()
    crosswalk_lookup = crosswalk_df.set_index("iso_id").to_dict(orient="index")

    rows: list[dict[str, object]] = []
    for _, row in mapping_df.iterrows():
        linked_ids = _split_ids(row["linked_ids"])
        metric_ids = _split_ids(row["metric_ids"])
        metric_descriptions = " | ".join(f"{metric_id}: {metric_lookup.get(metric_id, '')}" for metric_id in metric_ids)
        if row["framework"] == "ISO27001:2022":
            source_row = iso_lookup[row["id"]]
            official_crosswalk = crosswalk_lookup.get(row["id"], {})
            reference_context = source_row.get("domain", "")
            official_links = _split_ids(official_crosswalk.get("nist_ids", ""))
        else:
            source_row = nist_lookup[row["id"]]
            reference_context = " | ".join(
                part
                for part in [source_row.get("function", ""), source_row.get("category", "")]
                if part
            )
            official_links = _split_ids(source_row.get("linked_iso_ids", ""))
        rows.append(
            {
                "review_item_id": f"{row['framework']}::{row['id']}",
                "framework": row["framework"],
                "id": row["id"],
                "title": row["title"],
                "gqm_ref": row["gqm_ref"],
                "uml_class": row["uml_class"],
                "metric_ids": ";".join(metric_ids),
                "metric_descriptions": metric_descriptions,
                "linked_ids": ";".join(linked_ids),
                "official_reference_links": ";".join(official_links),
                "reference_context": reference_context,
                "link_count": len(linked_ids),
                "priority_score": len(linked_ids) * 10 + len(metric_ids),
                "selection_reason": "high_link_density" if linked_ids else "no_crosswalk_links",
                "reviewer_id": "",
                "metric_fit": "",
                "uml_fit": "",
                "crosswalk_fit": "",
                "overall_decision": "",
                "confidence": "",
                "notes": "",
            }
        )
    packet = pd.DataFrame(rows).sort_values(["framework", "priority_score", "id"], ascending=[True, False, True]).reset_index(drop=True)
    return packet


def select_priority_review_subset(packet: pd.DataFrame, sample_size: int = 60) -> pd.DataFrame:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if sample_size >= len(packet):
        return packet.copy()
    half = sample_size // 2
    remainder = sample_size - (half * 2)
    iso_packet = packet[packet["framework"] == "ISO27001:2022"].head(half + remainder)
    nist_packet = packet[packet["framework"] == "NIST-CSF-2.0"].head(half)
    subset = pd.concat([iso_packet, nist_packet], ignore_index=True)
    return subset.sort_values(["framework", "priority_score", "id"], ascending=[True, False, True]).reset_index(drop=True)


def _build_review_instructions(sample_size: int) -> str:
    return f"""# Semantic Review Packet

This packet is intended for two independent reviewers who assess the semantic quality of the standards mapping artifact.

## Files

- `semantic_review_master.csv`: full artifact-wide review inventory
- `semantic_review_priority_sample.csv`: recommended priority subset ({sample_size} rows)
- `reviewer_template_a.csv`: blank template for reviewer A
- `reviewer_template_b.csv`: blank template for reviewer B

## Judgement rubric

- `metric_fit`: `yes`, `partial`, or `no`
- `uml_fit`: `yes`, `partial`, or `no`
- `crosswalk_fit`: `yes`, `partial`, or `no`
- `overall_decision`: `accept`, `minor_revision`, `major_revision`, or `reject`
- `confidence`: `1`, `2`, or `3`

Reviewers should fill only the judgement columns plus `reviewer_id` and `notes`.
The `official_reference_links` column is the machine-derived target crosswalk used for semantic checking.
After both templates are completed, run:

```powershell
python tools/score_semantic_reviews.py --review-a out/review/reviewer_template_a.csv --review-b out/review/reviewer_template_b.csv
```

Optional internal QA-only proxy adjudication:

```powershell
python scripts/run_proxy_semantic_reviews.py --sample-size {sample_size}
```
"""


def build_review_artifacts(root: str | Path, sample_size: int = 60) -> ReviewArtifacts:
    root = Path(root)
    out_dir = ensure_dir(root / "out" / "review")
    master_packet = build_semantic_review_packet(root)
    priority_packet = select_priority_review_subset(master_packet, sample_size=sample_size)

    master_path = write_frame(out_dir / "semantic_review_master.csv", master_packet)
    priority_path = write_frame(out_dir / "semantic_review_priority_sample.csv", priority_packet)
    reviewer_a = write_frame(out_dir / "reviewer_template_a.csv", priority_packet.copy())
    reviewer_b = write_frame(out_dir / "reviewer_template_b.csv", priority_packet.copy())
    instructions = write_text(out_dir / "README.md", _build_review_instructions(len(priority_packet)))
    return ReviewArtifacts(
        master_packet=master_path,
        priority_packet=priority_path,
        reviewer_template_a=reviewer_a,
        reviewer_template_b=reviewer_b,
        instructions=instructions,
    )


def _normalized_value(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _cohen_kappa_or_unity(left: pd.Series, right: pd.Series) -> float:
    labels = sorted(set(left.tolist()) | set(right.tolist()))
    if len(labels) <= 1:
        return 1.0 if (left == right).all() else float("nan")
    return float(cohen_kappa_score(left, right))


def _expected_metrics_and_class(identifier: str) -> tuple[set[str], str]:
    metric_ids, uml_class = metric_bundle_for_identifier(identifier)
    return set(_split_ids(metric_ids)), uml_class


def _exact_or_partial_match(actual: set[str], expected: set[str]) -> str:
    if actual == expected:
        return "yes"
    if actual & expected:
        return "partial"
    return "no"


def _strict_metric_fit(row: pd.Series) -> tuple[str, list[str]]:
    actual_metrics = set(_split_ids(row["metric_ids"]))
    expected_metrics, _ = _expected_metrics_and_class(str(row["id"]))
    verdict = _exact_or_partial_match(actual_metrics, expected_metrics)
    notes: list[str] = []
    if verdict == "partial":
        notes.append("metric bundle deviates from expected identifier profile")
    elif verdict == "no":
        notes.append("metric bundle does not match expected identifier profile")
    return verdict, notes


def _contextual_metric_fit(row: pd.Series) -> tuple[str, list[str]]:
    actual_metrics = set(_split_ids(row["metric_ids"]))
    expected_metrics, _ = _expected_metrics_and_class(str(row["id"]))
    verdict = _exact_or_partial_match(actual_metrics, expected_metrics)
    notes: list[str] = []
    if verdict == "no":
        notes.append("metric bundle does not match expected identifier profile")
        return verdict, notes
    if row["framework"] == "ISO27001:2022" and row["link_count"] >= 10 and actual_metrics <= {"HF_AWARENESS", "TCO_3Y"}:
        notes.append("dense governance crosswalk represented only by HF/TCO metrics")
        return "partial", notes
    if row["framework"] == "ISO27001:2022" and row["id"].startswith("A.6") and actual_metrics == {"HF_AWARENESS", "DR"}:
        notes.append("people-control evidence is limited to awareness and detection signals")
        return "partial", notes
    if verdict == "partial":
        notes.append("metric bundle only partially overlaps expected identifier profile")
    return verdict, notes


def _strict_uml_fit(row: pd.Series) -> tuple[str, list[str]]:
    _, expected_class = _expected_metrics_and_class(str(row["id"]))
    if str(row["uml_class"]) == expected_class:
        return "yes", []
    return "no", ["uml class does not match expected identifier profile"]


def _contextual_uml_fit(row: pd.Series) -> tuple[str, list[str]]:
    _, expected_class = _expected_metrics_and_class(str(row["id"]))
    if str(row["uml_class"]) != expected_class:
        return "no", ["uml class does not match expected identifier profile"]
    if row["link_count"] >= 10 and str(row["uml_class"]) in {"HumanFactorMetric", "AssetValue", "ImpactLevel", "EventPotential"}:
        return "partial", ["high crosswalk density is represented through a single UML evidence class"]
    return "yes", []


def _strict_crosswalk_fit(row: pd.Series) -> tuple[str, list[str]]:
    linked_ids = set(_split_ids(row["linked_ids"]))
    official_links = set(_split_ids(row["official_reference_links"]))
    if linked_ids == official_links:
        return "yes", []
    if linked_ids & official_links:
        return "partial", ["crosswalk overlaps official references but is not exact"]
    return "no", ["crosswalk does not align with official references"]


def _contextual_crosswalk_fit(row: pd.Series) -> tuple[str, list[str]]:
    linked_ids = set(_split_ids(row["linked_ids"]))
    official_links = set(_split_ids(row["official_reference_links"]))
    if linked_ids == official_links:
        if not official_links:
            return "partial", ["no official informative-reference crosswalk exists for this row"]
        if row["framework"] == "ISO27001:2022" and len(official_links) == 1:
            return "partial", ["crosswalk is exact but anchored by only one official informative reference"]
        return "yes", []
    if linked_ids & official_links:
        return "partial", ["crosswalk overlaps official references but is not exact"]
    return "no", ["crosswalk does not align with official references"]


def _overall_decision_from_verdicts(verdicts: list[str], profile: str) -> str:
    partial_count = sum(verdict == "partial" for verdict in verdicts)
    if "no" in verdicts:
        return "major_revision"
    if profile == "strict":
        return "minor_revision" if partial_count else "accept"
    if partial_count >= 2:
        return "major_revision"
    if partial_count == 1:
        return "minor_revision"
    return "accept"


def _confidence_from_verdicts(verdicts: list[str], official_links: list[str], profile: str) -> str:
    partial_count = sum(verdict == "partial" for verdict in verdicts)
    if "no" in verdicts:
        return "1"
    if profile == "strict":
        return "3" if partial_count == 0 else "2"
    if partial_count >= 2:
        return "1"
    if partial_count == 1:
        return "2"
    return "3" if official_links else "2"


def _apply_proxy_reviewer(packet: pd.DataFrame, profile: str, reviewer_id: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in packet.iterrows():
        if profile == "strict":
            metric_fit, metric_notes = _strict_metric_fit(row)
            uml_fit, uml_notes = _strict_uml_fit(row)
            crosswalk_fit, crosswalk_notes = _strict_crosswalk_fit(row)
        elif profile == "contextual":
            metric_fit, metric_notes = _contextual_metric_fit(row)
            uml_fit, uml_notes = _contextual_uml_fit(row)
            crosswalk_fit, crosswalk_notes = _contextual_crosswalk_fit(row)
        else:
            raise ValueError(f"Unknown proxy profile: {profile}")

        verdicts = [metric_fit, uml_fit, crosswalk_fit]
        note_parts = metric_notes + uml_notes + crosswalk_notes
        overall_decision = _overall_decision_from_verdicts(verdicts, profile=profile)
        confidence = _confidence_from_verdicts(verdicts, _split_ids(row["official_reference_links"]), profile=profile)

        filled = row.to_dict()
        filled.update(
            {
                "reviewer_id": reviewer_id,
                "metric_fit": metric_fit,
                "uml_fit": uml_fit,
                "crosswalk_fit": crosswalk_fit,
                "overall_decision": overall_decision,
                "confidence": confidence,
                "notes": " | ".join(note_parts) if note_parts else "exact rule match",
            }
        )
        rows.append(filled)
    return pd.DataFrame(rows)


def _build_proxy_methods_text() -> str:
    return """# Proxy Semantic Adjudication

This directory contains two automated reviewer passes over the semantic review priority sample.

## Profiles

- `proxy_strict_v1`: exact-profile reviewer; expects the metric bundle, UML class, and official crosswalk links to match the identifier-derived reference profile exactly.
- `proxy_contextual_v1`: conservative reviewer; keeps exact crosswalk checks but marks dense governance rows, single-link rows, and high-density single-class abstractions as partial rather than immediate acceptance.

## Interpretation

- These files are machine-generated proxy adjudications, not independent human expert reviews.
- They are intended to stress-test the semantic review workflow and to provide a reproducible agreement baseline.
- If independent reviewers complete the blank templates in `../`, those human sheets should take precedence over these proxy outputs.
- These outputs are QA-only and must not be cited as human semantic validation.
"""


def run_proxy_semantic_review(
    root: str | Path,
    sample_size: int = 60,
    output_dir: str | Path | None = None,
) -> ProxyReviewArtifacts:
    root = Path(root)
    review_artifacts = build_review_artifacts(root, sample_size=sample_size)
    packet = pd.read_csv(review_artifacts.priority_packet).fillna("")
    proxy_dir = ensure_dir(output_dir if output_dir is not None else root / "out" / "review" / "qa_only_not_validation")

    reviewer_strict_df = _apply_proxy_reviewer(packet, profile="strict", reviewer_id="proxy_strict_v1")
    reviewer_contextual_df = _apply_proxy_reviewer(packet, profile="contextual", reviewer_id="proxy_contextual_v1")

    reviewer_strict = write_frame(proxy_dir / "proxy_reviewer_strict.csv", reviewer_strict_df)
    reviewer_contextual = write_frame(proxy_dir / "proxy_reviewer_contextual.csv", reviewer_contextual_df)
    methods_md = write_text(proxy_dir / "README.md", _build_proxy_methods_text())
    agreement = score_semantic_reviews(reviewer_strict, reviewer_contextual, proxy_dir)
    return ProxyReviewArtifacts(
        reviewer_strict=reviewer_strict,
        reviewer_contextual=reviewer_contextual,
        agreement_summary_csv=agreement.summary_csv,
        agreement_disagreements_csv=agreement.disagreements_csv,
        agreement_summary_md=agreement.summary_md,
        methods_md=methods_md,
    )


def score_semantic_reviews(
    review_a_path: str | Path,
    review_b_path: str | Path,
    output_dir: str | Path,
) -> AgreementArtifacts:
    review_a = pd.read_csv(review_a_path).fillna("")
    review_b = pd.read_csv(review_b_path).fillna("")
    key = "review_item_id"
    merged = review_a.merge(review_b, on=key, suffixes=("_a", "_b"), how="inner")
    if len(merged) != len(review_a) or len(merged) != len(review_b):
        raise ValueError("Reviewer files must contain the same review_item_id set.")

    summary_rows: list[dict[str, object]] = []
    disagreement_rows: list[dict[str, object]] = []
    for column in REVIEW_JUDGMENT_COLUMNS:
        left = merged[f"{column}_a"].map(_normalized_value)
        right = merged[f"{column}_b"].map(_normalized_value)
        mask = left.notna() & right.notna()
        if mask.any():
            scored_left = left[mask]
            scored_right = right[mask]
            agreement = float((scored_left == scored_right).mean())
            kappa = _cohen_kappa_or_unity(scored_left, scored_right)
        else:
            agreement = float("nan")
            kappa = float("nan")
        summary_rows.append(
            {
                "field": column,
                "rows_scored_by_both": int(mask.sum()),
                "percent_agreement": agreement,
                "cohen_kappa": kappa,
            }
        )
        differing = merged[mask & (left != right)]
        for _, row in differing.iterrows():
            disagreement_rows.append(
                {
                    "review_item_id": row[key],
                    "field": column,
                    "framework": row["framework_a"],
                    "id": row["id_a"],
                    "title": row["title_a"],
                    "reviewer_a": row[f"{column}_a"],
                    "reviewer_b": row[f"{column}_b"],
                }
            )

    summary = pd.DataFrame(summary_rows)
    disagreements = pd.DataFrame(
        disagreement_rows,
        columns=[
            "review_item_id",
            "field",
            "framework",
            "id",
            "title",
            "reviewer_a",
            "reviewer_b",
        ],
    )
    out_dir = ensure_dir(output_dir)
    summary_csv = write_frame(out_dir / "agreement_summary.csv", summary)
    disagreements_csv = write_frame(out_dir / "review_disagreements.csv", disagreements)

    lines = ["# Review Agreement Summary", ""]
    for _, row in summary.iterrows():
        pct = "n/a" if pd.isna(row["percent_agreement"]) else f"{row['percent_agreement']:.3f}"
        kappa = "n/a" if pd.isna(row["cohen_kappa"]) else f"{row['cohen_kappa']:.3f}"
        lines.append(
            f"- `{row['field']}`: rows scored by both = {int(row['rows_scored_by_both'])}, "
            f"agreement = {pct}, kappa = {kappa}"
        )
    if not disagreements.empty:
        lines.extend(["", "## Disagreements", "", f"- Rows with at least one disagreement: {disagreements['review_item_id'].nunique()}"])
    summary_md = write_text(out_dir / "agreement_summary.md", "\n".join(lines) + "\n")
    return AgreementArtifacts(summary_csv=summary_csv, disagreements_csv=disagreements_csv, summary_md=summary_md)
