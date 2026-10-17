"""基础指标：每个榜的名次变化，以及每部剧的增量和增速。其他分析器都建立在它上面。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from radar.analysis.util import ratio, rounded
from radar.core.registry import ANALYZERS
from radar.core.text import clean_tags
from radar.core.timeutil import days_between

COUNTERS = ("heat", "fav", "like", "rating_count", "review_count")
CATEGORY_BOARDS = ("real", "ai", "comic")


def _board_moves(h, board: str) -> Optional[Dict[str, Any]]:
    days = h.board_days(board)
    if not days:
        return None
    latest_day, latest = days[-1]
    prev_day, prev = (days[-2] if len(days) > 1 else (None, None))
    seen_before: set = set()
    for _, ranks in days[:-1]:
        seen_before.update(ranks)
    entries: List[Dict[str, Any]] = []
    for item_id, rank in sorted(latest.items(), key=lambda kv: kv[1]):
        streak = 0
        for _, ranks in reversed(days):
            if item_id not in ranks:
                break
            streak += 1
        history = [(d, r[item_id]) for d, r in days if item_id in r]
        if prev is None:
            badge = None  # 第一天没有可比的数据
        elif item_id not in seen_before:
            badge = "new"
        elif item_id not in prev:
            badge = "back"
        else:
            badge = None
        entries.append({
            "id": item_id,
            "rank": rank,
            "delta": (prev[item_id] - rank) if prev and item_id in prev else None,
            "badge": badge,
            "streak": streak,
            "best": min(r for _, r in history),
            "days_on": len(history),
            "first_on": history[0][0],
        })
    dropped = []
    if prev:
        dropped = [{"id": i, "last_rank": r} for i, r in sorted(prev.items(), key=lambda kv: kv[1]) if i not in latest]
    return {"date": latest_day, "prev_date": prev_day, "board_days": len(days), "entries": entries, "dropped": dropped}


@ANALYZERS.register("metrics", order=10)
def metrics(ctx) -> Dict[str, Any]:
    h = ctx.history
    cur = h.latest
    prev = h.previous()
    s3, s7 = h.ago(3), h.ago(7)
    gap = days_between(prev["date"], cur["date"]) if prev else None
    max_age = int(ctx.params.get("new_drama_max_age_days", 7))
    min_heat = float(ctx.params.get("min_heat_for_rate", 5_000_000))

    boards: Dict[str, Any] = {}
    placement: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for board in h.board_ids():
        moves = _board_moves(h, board)
        if not moves:
            continue
        moves["label"] = ctx.board_label(board)
        boards[board] = moves
        for e in moves["entries"]:
            placement.setdefault(e["id"], {})[board] = e

    dramas: Dict[str, Dict[str, Any]] = {}
    for item_id, it in (cur.get("items") or {}).items():
        meta = h.catalog.get(item_id) or {}
        before = h.item(prev, item_id)
        row: Dict[str, Any] = {
            "id": item_id,
            "title": it.get("title") or meta.get("title") or item_id,
            "tags": clean_tags(it.get("tags") or meta.get("tags")),
            "status_tags": it.get("status_tags") or [],
        }
        for key in COUNTERS + ("rating", "episodes", "first_visible", "heat_exact"):
            if it.get(key) is not None:
                row[key] = it[key]
        first_visible = it.get("first_visible") or meta.get("first_visible")
        row["age_days"] = days_between(first_visible, cur["date"]) if first_visible else None
        row["is_new"] = bool((row["age_days"] is not None and row["age_days"] <= max_age) or "新剧" in row["status_tags"])

        for key in COUNTERS:
            now, then = it.get(key), (before or {}).get(key)
            row[f"d_{key}"] = round((now - then) / gap) if gap and now is not None and then is not None else None
        prev_heat = (before or {}).get("heat")
        row["r_heat"] = rounded(ratio(row["d_heat"], prev_heat)) if prev_heat and prev_heat >= min_heat else None
        for label, snap in (("d3", s3), ("d7", s7)):
            for key in ("heat", "fav"):
                old = (h.item(snap, item_id) or {}).get(key)
                row[f"{label}_{key}"] = (it[key] - old) if snap and it.get(key) is not None and old is not None else None

        spots = placement.get(item_id, {})
        row["ranks"] = {b: e["rank"] for b, e in spots.items()}
        row["deltas"] = {b: e["delta"] for b, e in spots.items() if e["delta"] is not None}
        row["badges"] = {b: e["badge"] for b, e in spots.items() if e["badge"]}
        row["on_board"] = bool(spots)
        if row["deltas"]:
            best_board = max(row["deltas"], key=lambda b: row["deltas"][b])
            row["best_delta"], row["best_delta_board"] = row["deltas"][best_board], best_board
        kinds = [b for b in CATEGORY_BOARDS if b in spots] or [b for b in CATEGORY_BOARDS if b in (meta.get("boards_seen") or [])]
        row["kind"] = kinds[0] if kinds else "unknown"
        adaptation = meta.get("adaptation")
        if adaptation:
            row["adaptation"] = adaptation
        dramas[item_id] = row

    return {
        "date": cur["date"],
        "prev_date": prev["date"] if prev else None,
        "gap": gap,
        "d3_date": s3["date"] if s3 else None,
        "d7_date": s7["date"] if s7 else None,
        "history_days": len(h.snaps),
        "boards": boards,
        "dramas": dramas,
    }
