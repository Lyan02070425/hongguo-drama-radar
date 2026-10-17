"""看板「榜单」页：每个官方榜的完整排名，附上名次变化、增量和题材。"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from radar.core.registry import ANALYZERS

ROW_KEYS = (
    "title", "tags", "status_tags", "heat", "d_heat", "r_heat", "fav", "d_fav", "like", "d_like",
    "rating", "rating_count", "review_count", "d_review_count", "age_days", "is_new", "episodes", "kind",
)


@ANALYZERS.register("boards", depends=["metrics"], order=20)
def boards(ctx) -> Dict[str, Any]:
    m = ctx.results["metrics"]
    dramas = m["dramas"]
    out: Dict[str, Any] = {"date": m["date"], "prev_date": m["prev_date"], "boards": {}}
    for board, data in m["boards"].items():
        rows = []
        for e in data["entries"]:
            d = dramas.get(e["id"], {})
            row = dict(e)
            row.update({k: d[k] for k in ROW_KEYS if d.get(k) is not None})
            if d.get("adaptation"):
                row["adapted"] = d["adaptation"]["platform"]
            rows.append(row)
        heats = [r.get("heat") or 0 for r in rows]
        ages = [r["age_days"] for r in rows if r.get("age_days") is not None]
        tag_counts = Counter(t for r in rows for t in r.get("tags", []))
        out["boards"][board] = {
            "label": data["label"],
            "date": data["date"],
            "prev_date": data["prev_date"],
            "rows": rows,
            "dropped": [dict(x, title=ctx.history.title(x["id"])) for x in data["dropped"]],
            "summary": {
                "count": len(rows),
                "total_heat": sum(heats),
                "new_entries": sum(1 for r in rows if r.get("badge") == "new"),
                "back_entries": sum(1 for r in rows if r.get("badge") == "back"),
                "dropped": len(data["dropped"]),
                "new_dramas": sum(1 for r in rows if r.get("is_new")),
                "median_age": sorted(ages)[len(ages) // 2] if ages else None,
                "top_tags": [t for t, _ in tag_counts.most_common(5)],
            },
        }
    return out
