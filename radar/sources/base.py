"""数据源接口。新增平台（抖音、DataEye、海外 App……）时实现一个 Source 子类并注册即可。

快照格式对所有数据源统一（详见 docs/DATA.md）：

    {
      "schema": 1, "source": "hongguo", "date": "2026-10-17", "fetched_at": "...Z",
      "stale": false,
      "boards": {"hot": {"label": "热播榜", "label_date": "2026-10-17",
                          "items": [{"id": "...", "rank": 1, "heat": 92000000}]}},
      "items": {"<id>": {"title": "...", "tags": [...], "heat": 92004321, "fav": ..., ...}},
      "watchlist": [...], "errors": [...]
    }

分析器只依赖这个格式，不关心数据是从哪个平台来的。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from radar.core.config import Config
from radar.core.store import Store

SCHEMA_VERSION = 1


class CollectError(Exception):
    """数据不可信，本次不写快照。"""


@dataclass
class CollectResult:
    status: str  # "new" 新快照 | "exists" 当天已有 | "stale" 官方还没刷新
    snapshot: Optional[Dict[str, Any]] = None
    message: str = ""


class Source(ABC):
    id: str = ""
    label: str = ""

    def __init__(self, config: Config, store: Store, log: Callable[[str], None] = print) -> None:
        self.config = config
        self.settings = config.source(self.id)
        self.store = store
        self.log = log

    @abstractmethod
    def board_labels(self) -> Dict[str, str]:
        """榜单 id → 中文名，按展示顺序。"""

    @abstractmethod
    def collect(self, batch: str, force: bool = False, allow_stale: bool = False) -> CollectResult:
        """采集一个批次。成功时返回快照（调用方负责保存）。"""

    def item_url(self, item_id: str) -> Optional[str]:
        """单部剧的官方页面地址，看板上用来跳转。"""
        return None

    def describe(self) -> Dict[str, Any]:
        return {"id": self.id, "label": self.label, "boards": self.board_labels()}
