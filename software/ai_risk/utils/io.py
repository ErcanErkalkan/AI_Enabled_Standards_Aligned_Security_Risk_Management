from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: str | Path, payload: object) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_text(path: str | Path, content: str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return path


def write_rows(path: str | Path, rows: Iterable[Mapping[str, object]], fieldnames: list[str]) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_frame(path: str | Path, frame: pd.DataFrame, index: bool = False) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    frame.to_csv(path, index=index)
    return path

