from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.review import build_review_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build semantic review packets and dual-rater templates.")
    parser.add_argument("--sample-size", type=int, default=60, help="Priority sample size for reviewer templates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = build_review_artifacts(ROOT, sample_size=args.sample_size)
    print(f"Master review packet: {artifacts.master_packet}")
    print(f"Priority review packet: {artifacts.priority_packet}")
    print(f"Reviewer template A: {artifacts.reviewer_template_a}")
    print(f"Reviewer template B: {artifacts.reviewer_template_b}")
    print(f"Instructions: {artifacts.instructions}")


if __name__ == "__main__":
    main()
