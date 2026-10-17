"""快照、目录（catalog）和状态文件的读写。

- 快照 `data/snapshots/<source>/YYYY-MM-DD.json`：每个批次一份，只追加不修改，是唯一的原始数据。
- 目录 `data/catalog/<source>.json`：每部剧不常变的信息（简介、封面、改编来源、首次出现日期等），每次采集更新。
- 状态 `data/state/<source>/*.json`：采集过程中的缓存，比如观察列表的解析结果。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from radar.core.config import Paths


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, obj: Any, compact: bool = False, sort_keys: bool = True) -> None:
    """原子写入：先写临时文件再替换，进程中途被杀也不会留下半个文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)
    else:
        text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=sort_keys)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.write("\n")
        os.chmod(tmp, 0o644)  # mkstemp 默认 0600，部署到 Pages 前需要可读
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Store:
    def __init__(self, paths: Paths, source: str) -> None:
        self.paths = paths
        self.source = source

    # 快照
    def snapshot_path(self, day: str) -> Path:
        return self.paths.snapshots(self.source) / f"{day}.json"

    def dates(self) -> List[str]:
        folder = self.paths.snapshots(self.source)
        if not folder.exists():
            return []
        return sorted(p.stem for p in folder.glob("????-??-??.json"))

    def exists(self, day: str) -> bool:
        return self.snapshot_path(day).exists()

    def load(self, day: str) -> Optional[Dict[str, Any]]:
        return read_json(self.snapshot_path(day))

    def save(self, snapshot: Dict[str, Any]) -> Path:
        path = self.snapshot_path(snapshot["date"])
        write_json(path, snapshot, compact=True)
        return path

    def latest(self, before: Optional[str] = None) -> Optional[Dict[str, Any]]:
        days = [d for d in self.dates() if before is None or d < before]
        return self.load(days[-1]) if days else None

    def load_range(self, start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
        out = []
        for day in self.dates():
            if (start and day < start) or (end and day > end):
                continue
            snap = self.load(day)
            if snap:
                out.append(snap)
        return out

    # 目录
    def load_catalog(self) -> Dict[str, Dict[str, Any]]:
        return read_json(self.paths.catalog(self.source), {}) or {}

    def save_catalog(self, catalog: Dict[str, Dict[str, Any]]) -> None:
        write_json(self.paths.catalog(self.source), catalog)

    # 状态
    def load_state(self, name: str, default: Any = None) -> Any:
        return read_json(self.paths.state(self.source) / f"{name}.json", default)

    def save_state(self, name: str, obj: Any) -> None:
        write_json(self.paths.state(self.source) / f"{name}.json", obj)
