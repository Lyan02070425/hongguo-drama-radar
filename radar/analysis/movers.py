"""看板「飙升」页：按不同口径排出涨得最快（和跌得最快）的剧。"""

from __future__ import annotations

from typing import Any, Dict, List

from radar.analysis.util import pick, top
from radar.core.registry import ANALYZERS

ITEM_KEYS = ("id", "title", "tags", "heat", "fav", "rating", "age_days", "is_new", "ranks", "kind", "status_tags")

# key, 名称, 取值字段, 单位, 说明, 方向
LISTS = [
    ("rank_up", "名次上升", "best_delta", "位", "各榜里名次上升最多的一次", "desc"),
    ("heat", "热度日增", "d_heat", "热度", "比上一份快照多出的热度（按天平均）", "desc"),
    ("heat_rate", "热度增长率", "r_heat", "%", "热度日增 ÷ 昨天热度；昨天热度太低的不计", "desc"),
    ("fav", "收藏日增", "d_fav", "收藏", "每天新增收藏数，最接近「新观众」的信号", "desc"),
    ("like", "点赞日增", "d_like", "点赞", "每天新增点赞数", "desc"),
    ("review", "评论日增", "d_review_count", "评论", "每天新增评论数，反映讨论度", "desc"),
    ("rating_count", "评分人数日增", "d_rating_count", "人", "每天新增评分人数", "desc"),
    ("heat_7d", "7 日热度增量", "d7_heat", "热度", "和约 7 天前相比", "desc"),
    ("fav_7d", "7 日收藏增量", "d7_fav", "收藏", "和约 7 天前相比", "desc"),
    ("heat_drop", "热度下滑", "d_heat", "热度", "热度日减最多", "asc"),
    ("rank_down", "名次下滑", "worst_delta", "位", "各榜里名次下降最多的一次", "asc"),
]


@ANALYZERS.register("movers", depends=["metrics"], order=30)
def movers(ctx) -> Dict[str, Any]:
    m = ctx.results["metrics"]
    n = int(ctx.params.get("top_n", 50))
    rows: List[Dict[str, Any]] = []
    for d in m["dramas"].values():
        row = dict(d)
        if d.get("deltas"):
            worst = min(d["deltas"], key=lambda b: d["deltas"][b])
            row["worst_delta"], row["worst_delta_board"] = d["deltas"][worst], worst
        rows.append(row)

    lists = {}
    for key, label, field, unit, desc, direction in LISTS:
        chosen = top(rows, field, n, reverse=(direction == "desc"), positive_only=True)
        items = []
        for r in chosen:
            item = pick(r, ITEM_KEYS)
            item["value"] = r[field]
            board = r.get("best_delta_board") if field == "best_delta" else r.get("worst_delta_board") if field == "worst_delta" else None
            if board:
                item["board"] = board
                item["board_label"] = ctx.board_label(board)
                item["rank"] = r["ranks"].get(board)
            items.append(item)
        lists[key] = {"label": label, "field": field, "unit": unit, "desc": desc, "items": items}

    new_entries = []
    for r in rows:
        if "new" in r.get("badges", {}).values():
            boards = [b for b, v in r["badges"].items() if v == "new"]
            best = min(boards, key=lambda b: r["ranks"][b])
            item = pick(r, ITEM_KEYS)
            item.update(value=r["ranks"][best], board=best, board_label=ctx.board_label(best), rank=r["ranks"][best])
            new_entries.append(item)
    new_entries.sort(key=lambda x: x["value"])
    lists["new_entries"] = {"label": "新上榜", "field": "rank", "unit": "名", "desc": "之前从没上过这个榜，今天第一次上榜", "items": new_entries[:n]}

    return {"date": m["date"], "prev_date": m["prev_date"], "gap": m["gap"], "lists": lists}
