from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.review import score_semantic_reviews


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score agreement between two completed semantic review sheets.")
    parser.add_argument("--review-a", required=True, help="Path to reviewer A CSV.")
    parser.add_argument("--review-b", required=True, help="Path to reviewer B CSV.")
    parser.add_argument("--output-dir", default="out/review", help="Directory for agreement outputs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = score_semantic_reviews(args.review_a, args.review_b, ROOT / args.output_dir)
    print(f"Agreement summary: {artifacts.summary_csv}")
    print(f"Disagreements: {artifacts.disagreements_csv}")
    print(f"Markdown summary: {artifacts.summary_md}")


if __name__ == "__main__":
    main()
