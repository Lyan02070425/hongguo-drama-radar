"""看板「题材」页：哪些题材正热、哪些在升温、新剧扎堆在哪些题材、题材怎么组合。

口径说明：
- 一部剧有多个题材标签（榜单页的 3 个分类），会同时计入每个标签，所以各题材的热度占比加起来超过 100%。
- 热度占比 = 带这个标签的剧的热度之和 ÷ 整个榜的热度之和。
- 动量 = 今天的热度占比 − 约 N 天前的热度占比（单位：百分点）。历史不足 N 天时，和最早一份比，并注明对比日期。
- 超配倍数 = 新剧里带这个题材的比例 ÷ 老剧里带这个题材的比例；大于 1 说明新剧在往这个方向挤。
- 「漫剧」这类形式标签不算题材，在 config.toml 的 analysis.format_tags 里配置。
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, List, Optional

from radar.analysis.util import rounded
from radar.core.registry import ANALYZERS
from radar.core.text import clean_tags
from radar.core.timeutil import days_between

DEFAULT_FORMAT_TAGS = ["漫剧", "AI剧", "真人剧", "短剧"]


def _tags_of(h, snap, item_id: str, exclude: set) -> List[str]:
    it = h.item(snap, item_id) or {}
    tags = it.get("tags") or (h.catalog.get(item_id) or {}).get("tags") or []
    return [t for t in clean_tags(tags) if t not in exclude]


def board_tag_stats(h, snap, board: str, exclude: set) -> Dict[str, Dict[str, Any]]:
    data = (snap.get("boards") or {}).get(board) or {}
    items = data.get("items", [])
    total_heat = sum(x.get("heat") or 0 for x in items) or 1
    n = len(items) or 1
    acc: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "heat": 0, "rank_sum": 0, "ids": []})
    for x in items:
        for tag in _tags_of(h, snap, x["id"], exclude):
            a = acc[tag]
            a["count"] += 1
            a["heat"] += x.get("heat") or 0
            a["rank_sum"] += x["rank"]
            a["ids"].append(x["id"])
    return {
        tag: {
            "count": a["count"],
            "count_share": rounded(a["count"] / n),
            "heat": a["heat"],
            "heat_share": rounded(a["heat"] / total_heat),
            "avg_rank": round(a["rank_sum"] / a["count"], 1),
            "ids": a["ids"],
        }
        for tag, a in acc.items()
    }


@ANALYZERS.register("tags", depends=["metrics"], order=30)
def tags(ctx) -> Dict[str, Any]:
    h = ctx.history
    m = ctx.results["metrics"]
    params = ctx.params
    exclude = set(params.get("format_tags", DEFAULT_FORMAT_TAGS))
    momentum_days = int(params.get("tag_momentum_days", 7))
    min_count = int(params.get("min_tag_count", 3))
    dramas = m["dramas"]

    # 每个榜单日、每个榜的题材统计（导出 CSV 也用）
    by_date: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for snap in h.fresh:
        by_date[snap["date"]] = {b: board_tag_stats(h, snap, b, exclude) for b in h.board_ids() if b in (snap.get("boards") or {})}
    ctx.shared["tag_stats_by_date"] = by_date
    dates = sorted(by_date)
    if not dates:
        return {"date": m["date"], "boards": {}}
    latest_date = dates[-1]
    baseline_date: Optional[str] = None
    for d in reversed(dates[:-1]):
        if days_between(d, latest_date) >= momentum_days:
            baseline_date = d
            break
    if baseline_date is None and len(dates) > 1:
        baseline_date = dates[0]

    boards_out: Dict[str, Any] = {}
    for board, stats in by_date[latest_date].items():
        base = (by_date.get(baseline_date) or {}).get(board, {}) if baseline_date else {}
        rows = []
        for tag, s in stats.items():
            b = base.get(tag)
            row = {k: s[k] for k in ("count", "count_share", "heat", "heat_share", "avg_rank")}
            row["tag"] = tag
            row["top"] = [{"id": i, "title": h.title(i)} for i in s["ids"][:3]]
            if baseline_date:
                row["momentum"] = rounded((s["heat_share"] - (b["heat_share"] if b else 0)) * 100, 2)
                row["count_delta"] = s["count"] - (b["count"] if b else 0)
                row["is_new_tag"] = b is None
            rows.append(row)
        rows.sort(key=lambda r: r["heat_share"], reverse=True)
        # 今天消失了的题材也要出现在降温榜里
        gone = []
        for tag, b in base.items():
            if tag not in stats and b["count"] >= min_count:
                gone.append({"tag": tag, "count": 0, "heat_share": 0, "momentum": rounded(-b["heat_share"] * 100, 2), "count_delta": -b["count"]})
        eligible = [r for r in rows if r["count"] >= min_count or (r.get("count_delta") or 0) <= -min_count]
        rising = sorted([r for r in eligible if (r.get("momentum") or 0) >= 0.05], key=lambda r: r["momentum"], reverse=True)[:15]
        falling = sorted([r for r in eligible + gone if (r.get("momentum") or 0) <= -0.05], key=lambda r: r["momentum"])[:15]  # 变化不到 0.05 个百分点的不算

        # 时间序列：当前热度占比前 12 的题材 + 升温榜前 5
        focus = [r["tag"] for r in rows[:12]] + [r["tag"] for r in rising[:5] if r["tag"] not in [x["tag"] for x in rows[:12]]]
        series = {
            tag: [
                {"date": d, "count": by_date[d].get(board, {}).get(tag, {}).get("count", 0),
                 "heat_share": by_date[d].get(board, {}).get(tag, {}).get("heat_share", 0)}
                for d in dates if board in by_date[d]
            ]
            for tag in focus
        }
        boards_out[board] = {"label": ctx.board_label(board), "tags": rows, "rising": rising, "falling": falling, "series": series}

    # 以下按「今天在任意榜上」的剧去重统计
    on_board = [d for d in dramas.values() if d.get("on_board")]
    clean = {d["id"]: [t for t in d.get("tags", []) if t not in exclude] for d in on_board}
    new_ids = [d["id"] for d in on_board if d.get("is_new")]
    old_ids = [d["id"] for d in on_board if not d.get("is_new")]
    all_counts = Counter(t for ts in clean.values() for t in ts)
    new_counts = Counter(t for i in new_ids for t in clean[i])
    old_counts = Counter(t for i in old_ids for t in clean[i])
    new_vs_all = []
    min_new = max(min_count, math.ceil(0.05 * len(new_ids)))  # 太少的不算「扎堆」
    for tag, c in new_counts.most_common():
        if c < min_new:
            continue
        # 新剧 vs 老剧：新剧里带这个题材的比例 ÷ 老剧里的比例
        share_new = c / len(new_ids)
        share_old = old_counts[tag] / len(old_ids) if old_ids else 0
        new_vs_all.append({"tag": tag, "new_count": c, "old_count": old_counts[tag], "all_count": all_counts[tag],
                           "share_new": rounded(share_new), "share_old": rounded(share_old),
                           "over_index": rounded(share_new / share_old, 2) if share_old else None})
    # 老剧里完全没有的题材（over_index 为 None）排最前，它们是全新冒出来的方向
    new_vs_all.sort(key=lambda r: (r["over_index"] is None, r["over_index"] or 0, r["new_count"]), reverse=True)

    pair_counts: Counter = Counter()
    pair_heat: Dict[tuple, int] = defaultdict(int)
    for d in on_board:
        for pair in combinations(sorted(set(clean[d["id"]])), 2):
            pair_counts[pair] += 1
            pair_heat[pair] += d.get("heat") or 0
    pairs = [{"tags": list(p), "count": c, "avg_heat": round(pair_heat[p] / c)} for p, c in pair_counts.most_common(25)]

    efficiency = []
    by_tag: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in on_board:
        for t in clean[d["id"]]:
            by_tag[t].append(d)
    for tag, rows in by_tag.items():
        if len(rows) < min_count:
            continue
        favs = [r["d_fav"] for r in rows if r.get("d_fav") is not None]
        ratings = [r["rating"] for r in rows if r.get("rating") is not None]
        efficiency.append({
            "tag": tag, "count": len(rows),
            "avg_heat": round(sum(r.get("heat") or 0 for r in rows) / len(rows)),
            "avg_d_fav": round(sum(favs) / len(favs)) if favs else None,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        })
    efficiency.sort(key=lambda r: (r["avg_d_fav"] is not None, r["avg_d_fav"] or 0, r["avg_heat"]), reverse=True)

    matrix_boards = [b for b in ("real", "ai", "comic") if b in by_date[latest_date]]
    top_tags = [t for t, _ in all_counts.most_common(15)]
    matrix = {
        "boards": [{"id": b, "label": ctx.board_label(b)} for b in matrix_boards],
        "tags": top_tags,
        "counts": [[by_date[latest_date][b].get(t, {}).get("count", 0) for b in matrix_boards] for t in top_tags],
    }

    return {
        "date": latest_date,
        "baseline_date": baseline_date,
        "momentum_days": momentum_days,
        "board_days": len(dates),
        "format_tags": sorted(exclude),
        "boards": boards_out,
        "new_vs_all": new_vs_all[:20],
        "new_dramas": len(new_ids),
        "old_dramas": len(old_ids),
        "pairs": pairs,
        "efficiency": efficiency[:30],
        "matrix": matrix,
    }
