from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.settings import load_settings
from ai_risk.study import run_study


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the manuscript-aligned AI risk study.")
    parser.add_argument("--config", default="configs/default.yaml", help="Path to YAML config.")
    parser.add_argument("--profile", default="demo", help="Execution profile defined in the YAML config.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings(args.config, args.profile)
    result = run_study(settings)
    paper_summary = result["paper_summary"].iloc[0]
    print(f"Completed profile '{args.profile}'.")
    print(f"Artifact-default scorer F1={paper_summary['F1']:.3f}, AUROC={paper_summary['AUROC']:.3f}, Brier={paper_summary['Brier']:.3f}")


if __name__ == "__main__":
    main()
