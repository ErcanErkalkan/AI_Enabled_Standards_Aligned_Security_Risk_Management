from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class GlobalConfig:
    seed: int
    output_dir: str
    figures_dpi: int


@dataclass(frozen=True)
class Settings:
    root: Path
    profile_name: str
    global_cfg: GlobalConfig
    profile_cfg: dict[str, Any]

    @property
    def output_dir(self) -> Path:
        profile_output_dir = self.profile_cfg.get("output_dir", self.global_cfg.output_dir)
        return self.root / str(profile_output_dir)


def load_settings(config_path: str | Path, profile: str) -> Settings:
    config_path = Path(config_path).resolve()
    root = config_path.parent.parent.resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if profile not in raw["profiles"]:
        available = ", ".join(sorted(raw["profiles"]))
        raise KeyError(f"Unknown profile '{profile}'. Available: {available}")
    global_cfg = GlobalConfig(**raw["global"])
    return Settings(
        root=root,
        profile_name=profile,
        global_cfg=global_cfg,
        profile_cfg=raw["profiles"][profile],
    )
