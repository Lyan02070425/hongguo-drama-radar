"""看板「潜力新剧」页：给新剧和新上榜的剧打一个综合潜力分。

潜力分 = 几项指标在候选剧里的百分位加权平均（0~100）。权重在 config.toml 的
[analysis.potential_weights] 里调；某项没有数据（比如刚开始采集还没有增量）时，
这一项不参与，权重自动重新分配到其余几项。这是一个透明的经验规则，不是预测模型。
"""

from __future__ import annotations

from typing import Any, Dict

from radar.analysis.util import fmt_count, percentiles, pick
from radar.core.registry import ANALYZERS

DEFAULT_WEIGHTS = {"fav_growth": 0.35, "heat_growth_rate": 0.25, "rank_climb": 0.20, "rating": 0.20}
COMPONENT_FIELD = {"fav_growth": "d_fav", "heat_growth_rate": "r_heat", "rank_climb": "best_delta", "rating": "rating"}
ITEM_KEYS = ("id", "title", "tags", "status_tags", "heat", "fav", "d_fav", "r_heat", "rating", "age_days", "first_visible", "ranks", "kind", "episodes")


def _reason(component: str, row: Dict[str, Any], ctx) -> str:
    if component == "fav_growth":
        return f"收藏日增 {fmt_count(row['d_fav'], signed=True)}"
    if component == "heat_growth_rate":
        return f"热度日增 {row['r_heat']:+.1%}"
    if component == "rank_climb":
        return f"{ctx.board_label(row['best_delta_board'])}上升 {row['best_delta']} 位"
    return f"评分 {row['rating']}"


@ANALYZERS.register("potential", depends=["metrics"], order=30)
def potential(ctx) -> Dict[str, Any]:
    m = ctx.results["metrics"]
    weights = dict(DEFAULT_WEIGHTS)
    weights.update({k: float(v) for k, v in (ctx.params.get("potential_weights") or {}).items() if k in DEFAULT_WEIGHTS})
    candidates = {
        i: d for i, d in m["dramas"].items()
        if d.get("on_board") and (d.get("is_new") or "new" in (d.get("badges") or {}).values())
    }
    pcts = {c: percentiles({i: d.get(f) for i, d in candidates.items()}) for c, f in COMPONENT_FIELD.items()}

    items = []
    for item_id, row in candidates.items():
        parts, total_w, score = {}, 0.0, 0.0
        for comp, weight in weights.items():
            pct = pcts[comp].get(item_id)
            if pct is None or weight <= 0:
                continue
            parts[comp] = {"value": row.get(COMPONENT_FIELD[comp]), "pct": round(pct, 3)}
            total_w += weight
            score += weight * pct
        if not parts:
            continue
        best = sorted(parts, key=lambda c: parts[c]["pct"], reverse=True)[:2]
        item = pick(row, ITEM_KEYS)
        item.update(
            score=round(100 * score / total_w, 1),
            components=parts,
            reasons=[_reason(c, row, ctx) for c in best],
            new_on=[b for b, v in (row.get("badges") or {}).items() if v == "new"],
        )
        items.append(item)
    items.sort(key=lambda x: x["score"], reverse=True)
    available = [c for c in weights if pcts[c]]
    return {
        "date": m["date"],
        "weights": weights,
        "components_available": available,
        "candidates": len(candidates),
        "max_age_days": int(ctx.params.get("new_drama_max_age_days", 7)),
        "items": items[: int(ctx.params.get("top_n", 50))],
    }
