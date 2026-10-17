"""看板「内容结构」页：剧龄分布、新剧热度占比走势、改编来源、集数分布、上线到上榜要多久。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from radar.analysis.util import rounded
from radar.core.registry import ANALYZERS
from radar.core.timeutil import days_between

AGE_BUCKETS: List[Tuple[int, Optional[int], str]] = [
    (0, 3, "3 天内"), (4, 7, "4–7 天"), (8, 14, "8–14 天"), (15, 30, "15–30 天"), (31, 90, "1–3 个月"), (91, None, "3 个月以上"),
]
EPISODE_BUCKETS: List[Tuple[int, Optional[int], str]] = [
    (0, 60, "60 集以内"), (61, 100, "61–100 集"), (101, 200, "101–200 集"), (201, 500, "201–500 集"), (501, None, "500 集以上"),
]


def _bucket(value: Optional[int], buckets) -> str:
    if value is None:
        return "未知"
    for lo, hi, label in buckets:
        if value >= lo and (hi is None or value <= hi):
            return label
    return "未知"


def _first_visible(h, snap, item_id) -> Optional[str]:
    it = h.item(snap, item_id) or {}
    return it.get("first_visible") or (h.catalog.get(item_id) or {}).get("first_visible")


@ANALYZERS.register("lifecycle", depends=["metrics"], order=30)
def lifecycle(ctx) -> Dict[str, Any]:
    h = ctx.history
    m = ctx.results["metrics"]
    max_age = int(ctx.params.get("new_drama_max_age_days", 7))
    dramas = m["dramas"]
    out_boards: Dict[str, Any] = {}

    for board, data in m["boards"].items():
        rows = [dramas.get(e["id"], {}) for e in data["entries"]]
        total = sum(r.get("heat") or 0 for r in rows) or 1
        ages: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "heat": 0})
        eps: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "heat": 0})
        adapted = Counter()
        for r in rows:
            for acc, key in ((ages, _bucket(r.get("age_days"), AGE_BUCKETS)), (eps, _bucket(r.get("episodes"), EPISODE_BUCKETS))):
                acc[key]["count"] += 1
                acc[key]["heat"] += r.get("heat") or 0
            adapted[(r.get("adaptation") or {}).get("platform") or "未标注改编"] += 1
        order = [b[2] for b in AGE_BUCKETS] + ["未知"]
        eorder = [b[2] for b in EPISODE_BUCKETS] + ["未知"]
        out_boards[board] = {
            "label": data["label"],
            "age": [{"bucket": k, "count": ages[k]["count"], "heat_share": rounded(ages[k]["heat"] / total)} for k in order if k in ages],
            "episodes": [{"bucket": k, "count": eps[k]["count"], "heat_share": rounded(eps[k]["heat"] / total)} for k in eorder if k in eps],
            "adaptation": [{"platform": k, "count": c} for k, c in adapted.most_common()],
        }

    # 新剧热度占比的走势：每个榜单日里，上线不超过 max_age 天的剧贡献了多少热度
    trend: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for snap in h.fresh:
        for board in h.board_ids():
            data = (snap.get("boards") or {}).get(board)
            if not data:
                continue
            items = data.get("items", [])
            total = sum(x.get("heat") or 0 for x in items) or 1
            new_heat, new_count, known = 0, 0, 0
            for x in items:
                fv = _first_visible(h, snap, x["id"])
                if not fv:
                    continue
                known += 1
                if days_between(fv, snap["date"]) <= max_age:
                    new_heat += x.get("heat") or 0
                    new_count += 1
            trend[board].append({"date": snap["date"], "heat_share": rounded(new_heat / total), "count": new_count, "known": known})

    # 上线到首次上榜要几天（只统计采集期间第一次上榜的剧）
    first_board_day: Dict[str, str] = {}
    for snap in h.fresh:
        for data in (snap.get("boards") or {}).values():
            for x in data.get("items", []):
                first_board_day.setdefault(x["id"], snap["date"])
    start = h.fresh[0]["date"] if h.fresh else None
    lags = []
    for item_id, day in first_board_day.items():
        if day == start:
            continue  # 第一天就在榜上的，不知道是哪天上的榜
        fv = (h.catalog.get(item_id) or {}).get("first_visible")
        if fv:
            lags.append({"id": item_id, "title": h.title(item_id), "first_visible": fv, "first_on": day, "days": days_between(fv, day)})
    lags.sort(key=lambda r: r["first_on"], reverse=True)
    lag_values = sorted(r["days"] for r in lags)

    adapted_list = []
    for d in dramas.values():
        if d.get("on_board") and d.get("adaptation"):
            a = d["adaptation"]
            adapted_list.append({"id": d["id"], "title": d["title"], "platform": a["platform"], "work": a["work"],
                                 "author": a.get("author"), "best_rank": min(d["ranks"].values()), "heat": d.get("heat")})
    adapted_list.sort(key=lambda r: r["best_rank"])

    return {
        "date": m["date"],
        "max_age_days": max_age,
        "boards": out_boards,
        "new_heat_trend": trend,
        "time_to_board": {
            "count": len(lag_values),
            "median_days": lag_values[len(lag_values) // 2] if lag_values else None,
            "recent": lags[:30],
        },
        "adapted": adapted_list,
    }
