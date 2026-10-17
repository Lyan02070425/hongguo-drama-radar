"""读取 config.toml，并集中定义仓库里各个目录的位置。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.version_info < (3, 11):  # tomllib 从 3.11 起进入标准库
    raise SystemExit("drama-radar 需要 Python 3.11 及以上版本，当前是 %d.%d。" % sys.version_info[:2])

import tomllib

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    def snapshots(self, source: str) -> Path:
        return self.data / "snapshots" / source

    def catalog(self, source: str) -> Path:
        return self.data / "catalog" / f"{source}.json"

    def state(self, source: str) -> Path:
        return self.data / "state" / source

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def web(self) -> Path:
        return self.root / "web"


@dataclass
class Config:
    raw: Dict[str, Any]
    paths: Paths

    @property
    def general(self) -> Dict[str, Any]:
        return self.raw.get("general", {})

    @property
    def analysis(self) -> Dict[str, Any]:
        return self.raw.get("analysis", {})

    @property
    def reporters(self) -> Dict[str, Dict[str, Any]]:
        return self.raw.get("reporters", {})

    def source(self, source_id: str) -> Dict[str, Any]:
        return self.raw.get("sources", {}).get(source_id, {})

    def enabled_sources(self) -> List[str]:
        return [k for k, v in self.raw.get("sources", {}).items() if v.get("enabled", True)]

    @property
    def tz_offset(self) -> int:
        return int(self.general.get("timezone_offset_hours", 8))

    @property
    def cutoff_hour(self) -> int:
        return int(self.general.get("batch_cutoff_hour", 9))


def load_config(path: Optional[Path] = None, root: Optional[Path] = None) -> Config:
    root = Path(root) if root else ROOT
    path = Path(path) if path else root / "config.toml"
    raw: Dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    return Config(raw=raw, paths=Paths(root))
