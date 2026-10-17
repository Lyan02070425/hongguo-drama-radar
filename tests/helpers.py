"""测试工具：临时仓库目录、合成快照。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from radar.core.config import ROOT, Config, Paths

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def temp_config(raw: Optional[Dict[str, Any]] = None) -> Config:
    """一个临时仓库根目录：带上 web/，数据目录是空的。"""
    root = Path(tempfile.mkdtemp(prefix="radar-test-"))
    shutil.copytree(ROOT / "web", root / "web")
    raw = raw or {}
    raw.setdefault("sources", {}).setdefault("hongguo", {})
    return Config(raw=raw, paths=Paths(root))


def snapshot(date: str, boards: Dict[str, List[tuple]], items: Dict[str, Dict[str, Any]], stale: bool = False) -> Dict[str, Any]:
    """boards: {"hot": [(id, heat), ...]}，按顺序就是名次。"""
    return {
        "schema": 1,
        "source": "hongguo",
        "date": date,
        "fetched_at": f"{date}T03:00:00Z",
        "stale": stale,
        "boards": {
            b: {"label": b, "label_date": date, "items": [{"id": i, "rank": n + 1, "heat": heat} for n, (i, heat) in enumerate(rows)]}
            for b, rows in boards.items()
        },
        "items": items,
        "watchlist": [],
        "errors": [],
    }
