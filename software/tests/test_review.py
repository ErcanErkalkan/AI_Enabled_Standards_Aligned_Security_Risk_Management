from __future__ import annotations

import pandas as pd

from ai_risk.reference_data import build_reference_bundle
from ai_risk.review import build_review_artifacts, run_proxy_semantic_review, score_semantic_reviews


def test_build_review_artifacts_creates_master_and_templates(tmp_path):
    build_reference_bundle(tmp_path)
    artifacts = build_review_artifacts(tmp_path, sample_size=12)

    master = pd.read_csv(artifacts.master_packet)
    priority = pd.read_csv(artifacts.priority_packet)
    assert len(master) == 199
    assert len(priority) == 12
    assert {"review_item_id", "metric_fit", "uml_fit", "crosswalk_fit", "overall_decision"}.issubset(master.columns)
    assert artifacts.instructions.exists()


def test_score_semantic_reviews_outputs_agreement_and_disagreements(tmp_path):
    build_reference_bundle(tmp_path)
    artifacts = build_review_artifacts(tmp_path, sample_size=6)
    review_a = pd.read_csv(artifacts.reviewer_template_a)
    review_b = pd.read_csv(artifacts.reviewer_template_b)

    for frame in (review_a, review_b):
        frame["reviewer_id"] = "rater"
        frame["metric_fit"] = "yes"
        frame["uml_fit"] = "yes"
        frame["crosswalk_fit"] = "yes"
        frame["overall_decision"] = "accept"
        frame["confidence"] = "3"

    review_b.loc[0, "overall_decision"] = "major_revision"

    review_a_path = tmp_path / "review_a.csv"
    review_b_path = tmp_path / "review_b.csv"
    review_a.to_csv(review_a_path, index=False)
    review_b.to_csv(review_b_path, index=False)

    scored = score_semantic_reviews(review_a_path, review_b_path, tmp_path / "out" / "review")
    summary = pd.read_csv(scored.summary_csv)
    disagreements = pd.read_csv(scored.disagreements_csv)

    overall = summary.loc[summary["field"] == "overall_decision"].iloc[0]
    assert overall["rows_scored_by_both"] == 6
    assert overall["percent_agreement"] < 1.0
    assert not disagreements.empty


def test_score_semantic_reviews_returns_unity_kappa_for_single_label_agreement(tmp_path):
    build_reference_bundle(tmp_path)
    artifacts = build_review_artifacts(tmp_path, sample_size=4)
    review_a = pd.read_csv(artifacts.reviewer_template_a)
    review_b = pd.read_csv(artifacts.reviewer_template_b)

    for frame in (review_a, review_b):
        frame["reviewer_id"] = "rater"
        frame["metric_fit"] = "yes"
        frame["uml_fit"] = "yes"
        frame["crosswalk_fit"] = "yes"
        frame["overall_decision"] = "accept"
        frame["confidence"] = "3"

    review_a_path = tmp_path / "review_a.csv"
    review_b_path = tmp_path / "review_b.csv"
    review_a.to_csv(review_a_path, index=False)
    review_b.to_csv(review_b_path, index=False)

    scored = score_semantic_reviews(review_a_path, review_b_path, tmp_path / "out" / "review")
    summary = pd.read_csv(scored.summary_csv)
    disagreements = pd.read_csv(scored.disagreements_csv)

    metric_fit = summary.loc[summary["field"] == "metric_fit"].iloc[0]
    assert metric_fit["percent_agreement"] == 1.0
    assert metric_fit["cohen_kappa"] == 1.0
    assert disagreements.empty


def test_run_proxy_semantic_review_creates_completed_reviews_and_agreement(tmp_path):
    build_reference_bundle(tmp_path)
    artifacts = run_proxy_semantic_review(
        tmp_path,
        sample_size=12,
        output_dir=tmp_path / "out" / "review" / "qa_only_not_validation",
    )

    reviewer_strict = pd.read_csv(artifacts.reviewer_strict)
    reviewer_contextual = pd.read_csv(artifacts.reviewer_contextual)
    summary = pd.read_csv(artifacts.agreement_summary_csv)

    assert len(reviewer_strict) == 12
    assert len(reviewer_contextual) == 12
    assert set(reviewer_strict["reviewer_id"]) == {"proxy_strict_v1"}
    assert set(reviewer_contextual["reviewer_id"]) == {"proxy_contextual_v1"}
    assert summary["field"].tolist() == ["metric_fit", "uml_fit", "crosswalk_fit", "overall_decision"]
    assert summary["rows_scored_by_both"].tolist() == [12, 12, 12, 12]
    assert artifacts.methods_md.exists()
