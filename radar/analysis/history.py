"""把一个数据源的全部快照组织成便于分析的时间序列。所有分析器共用一个 History 对象。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from radar.core.timeutil import days_between, shift


class History:
    def __init__(self, source: str, snapshots: Iterable[Dict[str, Any]], catalog: Dict[str, Any],
                 board_order: Optional[List[str]] = None) -> None:
        self.source = source
        self.snaps: List[Dict[str, Any]] = sorted(snapshots, key=lambda s: s["date"])
        self.by_date = {s["date"]: s for s in self.snaps}
        self.dates = [s["date"] for s in self.snaps]
        self.catalog = catalog
        self.board_order = list(board_order or [])
        # 榜单日：去掉用 --allow-stale 写出的、榜单没刷新的快照，避免重复计入在榜天数
        self.fresh = [s for s in self.snaps if not s.get("stale")]
        self._rank_cache: Dict[Tuple[str, str], Dict[str, int]] = {}

    def __bool__(self) -> bool:
        return bool(self.snaps)

    @property
    def latest(self) -> Optional[Dict[str, Any]]:
        return self.snaps[-1] if self.snaps else None

    def previous(self, day: Optional[str] = None) -> Optional[Dict[str, Any]]:
        day = day or (self.latest or {}).get("date")
        earlier = [s for s in self.snaps if s["date"] < (day or "")]
        return earlier[-1] if earlier else None

    def on_or_before(self, day: str) -> Optional[Dict[str, Any]]:
        earlier = [s for s in self.snaps if s["date"] <= day]
        return earlier[-1] if earlier else None

    def ago(self, days: int, tolerance: int = 2, day: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """约 N 天前的快照：取「N 天前当天或更早、但不超过 N+tolerance 天」的最近一份。"""
        day = day or self.latest["date"]
        target = shift(day, -days)
        snap = self.on_or_before(target)
        if snap and days_between(snap["date"], day) <= days + tolerance:
            return snap
        return None

    @staticmethod
    def item(snap: Optional[Dict[str, Any]], item_id: str) -> Optional[Dict[str, Any]]:
        if not snap:
            return None
        return (snap.get("items") or {}).get(item_id)

    def ranks(self, snap: Optional[Dict[str, Any]], board: str) -> Dict[str, int]:
        if not snap:
            return {}
        key = (snap["date"], board)
        if key not in self._rank_cache:
            data = (snap.get("boards") or {}).get(board) or {}
            self._rank_cache[key] = {x["id"]: x["rank"] for x in data.get("items", [])}
        return self._rank_cache[key]

    def board_ids(self) -> List[str]:
        seen: List[str] = []
        for snap in self.snaps:
            for board in snap.get("boards") or {}:
                if board not in seen:
                    seen.append(board)
        # 按数据源声明的顺序（热播榜在前），快照文件里的键是按字母排的
        rank = {b: i for i, b in enumerate(self.board_order)}
        return sorted(seen, key=lambda b: (rank.get(b, len(rank)), b))

    def board_label(self, board: str) -> str:
        for snap in reversed(self.snaps):
            data = (snap.get("boards") or {}).get(board)
            if data and data.get("label"):
                return data["label"]
        return board

    def board_days(self, board: str) -> List[Tuple[str, Dict[str, int]]]:
        return [(s["date"], self.ranks(s, board)) for s in self.fresh if board in (s.get("boards") or {})]

    def title(self, item_id: str) -> str:
        for snap in reversed(self.snaps):
            it = self.item(snap, item_id)
            if it and it.get("title"):
                return it["title"]
        return (self.catalog.get(item_id) or {}).get("title") or item_id

    def series(self, item_id: str) -> List[Dict[str, Any]]:
        points = []
        for snap in self.snaps:
            it = self.item(snap, item_id)
            if not it:
                continue
            point = {k: it.get(k) for k in ("heat", "fav", "like", "rating", "rating_count", "review_count")}
            point["date"] = snap["date"]
            point["ranks"] = {b: self.ranks(snap, b)[item_id] for b in (snap.get("boards") or {}) if item_id in self.ranks(snap, b)}
            points.append(point)
        return points
