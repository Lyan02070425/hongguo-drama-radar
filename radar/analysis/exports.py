"""CSV 导出：长表格式，直接用 Excel、飞书表格或 pandas 打开做自己的分析。"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, Iterable, List

from radar.core.registry import ANALYZERS
from radar.core.timeutil import days_between


def _csv(header: List[str], rows: Iterable[List[Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return buf.getvalue()


def _join(values) -> str:
    return "|".join(values or [])


@ANALYZERS.register("exports", depends=["tags"], order=60)
def exports(ctx) -> Dict[str, Any]:
    h = ctx.history
    boards = h.board_ids()
    files = []

    def add(name: str, label: str, desc: str, header: List[str], rows: List[List[Any]]) -> None:
        ctx.emit(f"exports/{name}", _csv(header, rows))
        files.append({"path": f"exports/{name}", "label": label, "desc": desc, "rows": len(rows), "columns": header})

    drama_rows = []
    for snap in h.snaps:
        for item_id, it in (snap.get("items") or {}).items():
            fv = it.get("first_visible") or (h.catalog.get(item_id) or {}).get("first_visible")
            drama_rows.append([
                snap["date"], item_id, it.get("title"), it.get("heat"), int(bool(it.get("heat_exact"))), it.get("fav"), it.get("like"),
                it.get("rating"), it.get("rating_count"), it.get("review_count"), it.get("episodes"), fv,
                days_between(fv, snap["date"]) if fv else None, _join(it.get("tags")), _join(it.get("status_tags")),
                *[h.ranks(snap, b).get(item_id) for b in boards],
            ])
    add("drama_daily.csv", "每日剧集指标", "每天每部被追踪的剧一行：热度、收藏、点赞、评分、评论、各榜名次",
        ["date", "id", "title", "heat", "heat_exact", "fav", "like", "rating", "rating_count", "review_count", "episodes",
         "first_visible", "age_days", "tags", "status_tags", *[f"rank_{b}" for b in boards]], drama_rows)

    board_rows = []
    for snap in h.fresh:
        for board, data in (snap.get("boards") or {}).items():
            for x in data.get("items", []):
                board_rows.append([snap["date"], board, x["rank"], x["id"], h.title(x["id"]), x.get("heat")])
    add("board_daily.csv", "每日榜单", "每天每个榜的完整排名（热度为榜单页显示的值，取整到万）",
        ["date", "board", "rank", "id", "title", "heat"], board_rows)

    tag_rows = []
    for day, per_board in sorted((ctx.shared.get("tag_stats_by_date") or {}).items()):
        for board, stats in per_board.items():
            for tag, s in sorted(stats.items(), key=lambda kv: -kv[1]["heat"]):
                tag_rows.append([day, board, tag, s["count"], s["count_share"], s["heat"], s["heat_share"], s["avg_rank"]])
    add("tag_daily.csv", "每日题材统计", "每天每个榜里每个题材的部数、热度和占比",
        ["date", "board", "tag", "count", "count_share", "heat", "heat_share", "avg_rank"], tag_rows)

    cat_rows = []
    for item_id, meta in sorted(h.catalog.items()):
        a = meta.get("adaptation") or {}
        cat_rows.append([
            item_id, meta.get("title"), _join(meta.get("tags")), _join(meta.get("detail_tags")), meta.get("first_visible"),
            meta.get("episodes"), meta.get("first_seen"), meta.get("last_seen"), _join(meta.get("boards_seen")),
            a.get("platform"), a.get("work"), a.get("author"), _join(meta.get("cast")), meta.get("synopsis"),
        ])
    add("catalog.csv", "剧集目录", "每部出现过的剧一行：题材、上线日期、集数、改编来源、简介",
        ["id", "title", "tags", "detail_tags", "first_visible", "episodes", "first_seen", "last_seen", "boards_seen",
         "adapt_platform", "adapt_work", "adapt_author", "cast", "synopsis"], cat_rows)

    return {"date": h.latest["date"], "files": files}
