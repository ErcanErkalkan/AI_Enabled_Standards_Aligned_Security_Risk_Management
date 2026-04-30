from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.review import run_proxy_semantic_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated dual-rater proxy semantic adjudication.")
    parser.add_argument("--sample-size", type=int, default=60, help="Priority sample size for proxy review generation.")
    parser.add_argument(
        "--output-dir",
        default="out/review/qa_only_not_validation",
        help="Output directory for QA-only proxy reviews and agreement files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = run_proxy_semantic_review(ROOT, sample_size=args.sample_size, output_dir=ROOT / args.output_dir)
    print(f"Proxy reviewer (strict): {artifacts.reviewer_strict}")
    print(f"Proxy reviewer (contextual): {artifacts.reviewer_contextual}")
    print(f"Agreement summary: {artifacts.agreement_summary_csv}")
    print(f"Disagreements: {artifacts.agreement_disagreements_csv}")
    print(f"Markdown summary: {artifacts.agreement_summary_md}")
    print(f"Methods: {artifacts.methods_md}")


if __name__ == "__main__":
    main()
