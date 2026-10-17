"""数据状态：最新批次、历史天数、各榜日期、错误。看板顶部的状态栏用。"""

from __future__ import annotations

from typing import Any, Dict

from radar.core.registry import ANALYZERS
from radar.core.timeutil import utc_stamp


@ANALYZERS.register("status", order=5)
def status(ctx) -> Dict[str, Any]:
    h = ctx.history
    cur = h.latest
    return {
        "source": ctx.source.id,
        "label": ctx.source.label,
        "latest_date": cur["date"],
        "fetched_at": cur.get("fetched_at"),
        "stale": bool(cur.get("stale")),
        "first_date": h.dates[0],
        "history_days": len(h.dates),
        "dates": h.dates[-90:],
        "boards": {
            b: {"label": d.get("label") or ctx.board_label(b), "label_date": d.get("label_date"), "count": len(d.get("items", []))}
            for b in h.board_ids()
            if (d := (cur.get("boards") or {}).get(b))
        },
        "tracked": len(cur.get("items") or {}),
        "requests": cur.get("requests"),
        "errors": (cur.get("errors") or [])[:50],
        "error_count": len(cur.get("errors") or []),
        "watchlist": cur.get("watchlist") or [],
        "generated_at": utc_stamp(),
    }
