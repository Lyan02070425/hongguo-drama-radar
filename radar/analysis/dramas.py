"""单剧档案：每部出现过的剧一个历史文件（看板详情面板用），外加一个搜索索引。"""

from __future__ import annotations

from typing import Any, Dict

from radar.analysis.runner import dumps
from radar.core.registry import ANALYZERS

META_KEYS = ("tags", "detail_tags", "synopsis", "cover", "adaptation", "first_visible", "episodes", "cast", "first_seen", "last_seen", "boards_seen")


@ANALYZERS.register("dramas", depends=["metrics"], order=40)
def dramas(ctx) -> Dict[str, Any]:
    h = ctx.history
    m = ctx.results["metrics"]
    ids = set(h.catalog)
    for snap in h.snaps:
        ids.update((snap.get("items") or {}).keys())
    index = []
    for item_id in sorted(ids):
        points = h.series(item_id)
        if not points:
            continue
        meta = h.catalog.get(item_id) or {}
        best = {}
        for p in points:
            for board, rank in p["ranks"].items():
                best[board] = min(rank, best.get(board, rank))
        latest = m["dramas"].get(item_id) or {}
        record = {
            "id": item_id,
            "title": h.title(item_id),
            "url": ctx.source.item_url(item_id),
            "meta": {k: meta[k] for k in META_KEYS if meta.get(k)},
            "best_ranks": best,
            "latest": {k: latest[k] for k in ("ranks", "deltas", "d_heat", "d_fav", "r_heat", "age_days", "is_new", "kind") if latest.get(k) is not None},
            "points": points,
        }
        ctx.emit(f"dramas/{item_id}.json", dumps(record))
        index.append({
            "id": item_id,
            "title": record["title"],
            "tags": meta.get("tags") or [],
            "last_seen": points[-1]["date"],
            "best": min(best.values()) if best else None,
            "ranks": latest.get("ranks") or {},
            "heat": points[-1].get("heat"),
        })
    index.sort(key=lambda r: (r["last_seen"], r["heat"] or 0), reverse=True)  # 最近出现的在前，同一天按热度从高到低
    return {"date": m["date"], "count": len(index), "items": index}
