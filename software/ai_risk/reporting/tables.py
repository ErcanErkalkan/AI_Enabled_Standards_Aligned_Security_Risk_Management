from __future__ import annotations

from pathlib import Path

import pandas as pd

from ai_risk.utils.io import ensure_dir


def save_table(frame: pd.DataFrame, output_dir: str | Path, stem: str) -> tuple[Path, Path]:
    output_dir = ensure_dir(output_dir)
    csv_path = output_dir / f"{stem}.csv"
    tex_path = output_dir / f"{stem}.tex"
    frame.to_csv(csv_path, index=False)
    tex_path.write_text(frame.to_latex(index=False, float_format=lambda value: f"{value:.3f}", escape=False), encoding="utf-8")
    return csv_path, tex_path

