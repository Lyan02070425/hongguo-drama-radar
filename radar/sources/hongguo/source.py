"""红果数据源：每天采集 4 个官方热播榜的前 100 名，再补抓追踪集合里每部剧的详情。

访问方式：普通的 GET 请求，User-Agent 如实标明身份，不冒充搜索引擎爬虫；
相邻请求至少间隔 request_interval_seconds 秒，一天只在官方刷新后完整采集一次。
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from radar.core.http import FetchError, Fetcher
from radar.core.registry import SOURCES
from radar.core.text import parse_adaptation
from radar.core.timeutil import days_between, utc_stamp
from radar.sources.base import SCHEMA_VERSION, CollectError, CollectResult, Source
from radar.sources.hongguo.parse import (
    ParseError,
    extract_id,
    parse_detail_page,
    parse_rank_page,
    parse_search_page,
)

BOARDS: Dict[str, Tuple[str, str]] = {
    "hot": ("hot-drama", "热播榜"),
    "real": ("hot-real-drama", "真人剧热播榜"),
    "ai": ("hot-ai-drama", "AI剧热播榜"),
    "comic": ("hot-comic-drama", "漫剧热播榜"),
}

# 列表页拿到的字段（详情页没抓到时用它们兜底）
_LIST_FIELDS = ("title", "heat", "fav", "like", "rating")


@SOURCES.register("hongguo")
class HongguoSource(Source):
    id = "hongguo"
    label = "红果短剧"

    def __init__(self, config, store, log=print, fetcher: Optional[Fetcher] = None) -> None:
        super().__init__(config, store, log)
        s = self.settings
        self.base = s.get("base_url", "https://hongguoduanju.com").rstrip("/")
        self.board_ids = [b for b in s.get("boards", list(BOARDS)) if b in BOARDS]
        self.fetcher = fetcher or Fetcher(
            user_agent=s.get("user_agent", "drama-radar/0.1"),
            min_interval=float(s.get("request_interval_seconds", 1.0)),
            timeout=float(s.get("timeout_seconds", 20)),
        )

    # ---- 接口 ----
    def board_labels(self) -> Dict[str, str]:
        return {b: BOARDS[b][1] for b in self.board_ids}

    def item_url(self, item_id: str) -> str:
        return f"{self.base}/detail?series_id={item_id}"

    def collect(self, batch: str, force: bool = False, allow_stale: bool = False) -> CollectResult:
        if self.store.exists(batch) and not force:
            return CollectResult("exists", None, f"{batch} 的快照已存在（加 --force 覆盖）")

        boards, list_items = self._collect_boards(batch)
        previous = self.store.latest(before=batch)
        stale = previous is not None and self._same_boards(boards, previous)
        if stale and not allow_stale:
            return CollectResult("stale", None, "官方榜单和上一份快照完全相同，今天可能还没刷新，稍后再试")

        errors: List[Dict[str, str]] = []
        watch = self._resolve_watchlist(errors)
        tracked = self._tracked_ids(list_items, watch, batch)
        details = self._collect_details(tracked, errors) if self.settings.get("fetch_details", True) else {}

        catalog = self.store.load_catalog()
        items = self._merge(tracked, list_items, details, catalog, boards)
        snapshot = {
            "schema": SCHEMA_VERSION,
            "source": self.id,
            "date": batch,
            "fetched_at": utc_stamp(),
            "stale": bool(stale),
            "boards": boards,
            "items": items,
            "watchlist": watch,
            "errors": errors,
            "requests": self.fetcher.requests,
        }
        self._update_catalog(catalog, items, list_items, details, boards, batch)
        self.store.save_catalog(catalog)
        msg = f"{len(items)} 部剧，{sum(len(b['items']) for b in boards.values())} 个榜单条目，{self.fetcher.requests} 次请求"
        if errors:
            msg += f"，{len(errors)} 个错误"
        return CollectResult("new", snapshot, msg)

    # ---- 榜单 ----
    def _rank_url(self, board: str, page: int) -> str:
        slug = BOARDS[board][0]
        return f"{self.base}/rank/{slug}" + (f"?page={page}" if page > 1 else "")

    def _collect_boards(self, batch: str) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        max_pages = int(self.settings.get("max_pages", 5))
        min_items = int(self.settings.get("min_items_per_board", 80))
        boards: Dict[str, Any] = {}
        list_items: Dict[str, Dict[str, Any]] = {}
        for board in self.board_ids:
            entries: Dict[str, Dict[str, Any]] = {}
            label_date = None
            page, total = 1, 1
            while page <= min(total, max_pages):
                try:
                    parsed = parse_rank_page(self.fetcher.get(self._rank_url(board, page)), batch)
                except (FetchError, ParseError) as exc:
                    raise CollectError(f"{BOARDS[board][1]} 第 {page} 页：{exc}") from exc
                label_date = label_date or parsed["label_date"]
                total = parsed["pages"] or page
                offset = len(entries)
                for i, item in enumerate(parsed["items"]):
                    item.setdefault("rank", offset + i + 1)
                    if item["id"] not in entries:
                        entries[item["id"]] = item
                page += 1
            ranked = sorted(entries.values(), key=lambda x: x["rank"])
            if len(ranked) < min_items:
                raise CollectError(f"{BOARDS[board][1]} 只抓到 {len(ranked)} 部，少于 {min_items}，页面可能异常")
            boards[board] = {
                "label": BOARDS[board][1],
                "label_date": label_date,
                "items": [{"id": x["id"], "rank": x["rank"], "heat": x.get("heat")} for x in ranked],
            }
            for x in ranked:
                merged = list_items.setdefault(x["id"], {"boards": []})
                merged["boards"].append(board)
                for key, value in x.items():
                    if value not in (None, [], "") and key not in ("rank", "id"):
                        merged.setdefault(key, value)
            self.log(f"  {BOARDS[board][1]}：{len(ranked)} 部（{label_date or '无日期'}）")
        return boards, list_items

    @staticmethod
    def _same_boards(boards: Dict[str, Any], previous: Dict[str, Any]) -> bool:
        """名次和（取整到万的）热度全部和上一份相同，就是官方还没刷新。

        热度每天批量重算，刷新后前 100 名里总会有变化；只看名次不够，零星的名次变动在未刷新时也出现过。
        """
        prev_boards = previous.get("boards") or {}
        for board, data in boards.items():
            old = prev_boards.get(board)
            if not old:
                return False
            now = [(x["id"], x["rank"], x.get("heat")) for x in data["items"]]
            before = [(x["id"], x["rank"], x.get("heat")) for x in old.get("items", [])]
            if now != before:
                return False
        return True

    # ---- 追踪集合 ----
    def _tracked_ids(self, list_items: Dict[str, Any], watch: List[Dict[str, Any]], batch: str) -> List[str]:
        tracked: Set[str] = set(list_items)
        tracked.update(w["id"] for w in watch if w.get("id"))
        keep_days = int(self.settings.get("track_dropped_days", 14))
        for day in reversed(self.store.dates()):
            if day >= batch:
                continue
            if days_between(day, batch) > keep_days:
                break
            snap = self.store.load(day) or {}
            for data in (snap.get("boards") or {}).values():
                tracked.update(x["id"] for x in data.get("items", []))
        return sorted(tracked)

    def _resolve_watchlist(self, errors: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        entries = [str(e).strip() for e in self.settings.get("watchlist", []) if str(e).strip()]
        cache: Dict[str, Any] = self.store.load_state("watchlist", {}) or {}
        out = []
        for entry in entries:
            sid = extract_id(entry)
            if sid:
                out.append({"entry": entry, "status": "ok", "id": sid})
                continue
            if cache.get(entry, {}).get("status") == "ok":
                out.append(cache[entry])
                continue
            try:
                url = f"{self.base}/search/{urllib.parse.quote(entry)}"
                hits = [h for h in parse_search_page(self.fetcher.get(url)) if h["title"] == entry]
            except (FetchError, ParseError) as exc:
                errors.append({"stage": "watchlist", "id": entry, "message": str(exc)})
                out.append({"entry": entry, "status": "error"})
                continue
            if len(hits) == 1:
                result = {"entry": entry, "status": "ok", "id": hits[0]["id"]}
            else:
                result = {"entry": entry, "status": "not_found" if not hits else "ambiguous"}
            cache[entry] = result
            out.append(result)
        self.store.save_state("watchlist", cache)
        return out

    # ---- 详情 ----
    def _collect_details(self, ids: List[str], errors: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        details: Dict[str, Dict[str, Any]] = {}
        failed = 0
        self.log(f"  抓取 {len(ids)} 部剧的详情页…")
        for i, sid in enumerate(ids, 1):
            try:
                details[sid] = parse_detail_page(self.fetcher.get(self.item_url(sid)), self.config.tz_offset)
            except (FetchError, ParseError) as exc:
                failed += 1
                errors.append({"stage": "detail", "id": sid, "message": str(exc)})
            if i % 50 == 0:
                self.log(f"    {i}/{len(ids)}")
        ratio = failed / len(ids) if ids else 0
        limit = float(self.settings.get("max_detail_failure_ratio", 0.10))
        if ratio > limit:
            raise CollectError(f"详情页失败 {failed}/{len(ids)}，超过 {limit:.0%}，本次不写快照")
        return details

    # ---- 合并 ----
    @staticmethod
    def _merge(tracked, list_items, details, catalog, boards) -> Dict[str, Dict[str, Any]]:
        items: Dict[str, Dict[str, Any]] = {}
        for sid in tracked:
            li = list_items.get(sid, {})
            de = details.get(sid, {})
            known = catalog.get(sid, {})
            item: Dict[str, Any] = {}
            for key in _LIST_FIELDS:
                value = de.get(key) if de.get(key) is not None else li.get(key)
                if value is not None:
                    item[key] = value
            if "title" not in item and known.get("title"):
                item["title"] = known["title"]
            item["heat_exact"] = de.get("heat") is not None
            # 题材标签以榜单页的 3 个分类为准；不在榜上时用以前记下的，再不行用详情页的标签
            item["tags"] = li.get("tags") or known.get("tags") or de.get("detail_tags") or []
            item["status_tags"] = li.get("status_tags") or []
            for key in ("rating_count", "review_count", "episodes", "episodes_total", "status_code", "first_visible", "pay_type"):
                if de.get(key) is not None:
                    item[key] = de[key]
            if de.get("detail_tags"):
                item["detail_tags"] = de["detail_tags"]
            item["tracked_by"] = sorted(set(li.get("boards", [])) | ({"detail"} if de else set()))
            items[sid] = item
        return items

    @staticmethod
    def _update_catalog(catalog, items, list_items, details, boards, batch) -> None:
        for sid, item in items.items():
            entry = catalog.setdefault(sid, {"first_seen": batch})
            entry["last_seen"] = batch
            li = list_items.get(sid, {})
            de = details.get(sid, {})
            entry["title"] = item.get("title") or entry.get("title")
            if li.get("tags"):
                entry["tags"] = li["tags"]
            for key in ("detail_tags", "first_visible", "episodes", "cast"):
                if de.get(key):
                    entry[key] = de[key]
            synopsis = li.get("synopsis") or de.get("synopsis")
            if synopsis:
                entry["synopsis"] = synopsis
                entry["adaptation"] = parse_adaptation(synopsis)
            cover = li.get("cover") or de.get("cover")
            if cover:
                entry["cover"] = cover
            on = set(entry.get("boards_seen", []))
            on.update(li.get("boards", []))
            entry["boards_seen"] = sorted(on)
            if li.get("boards"):
                entry["last_on_board"] = batch
