"""「今日要点」：从各分析结果里挑出值得注意的变化，写成几句话。规则写死、可追溯，不用大模型。"""

from __future__ import annotations

from typing import Any, Dict, List

from radar.analysis.util import fmt_count
from radar.core.registry import ANALYZERS


def _first(lst: Dict[str, Any]) -> Dict[str, Any]:
    items = (lst or {}).get("items") or []
    return items[0] if items else {}


@ANALYZERS.register("insights", depends=["metrics", "boards", "movers", "potential", "tags", "lifecycle"], order=70)
def insights(ctx) -> Dict[str, Any]:
    r = ctx.results
    m, boards, movers, potential, tags, life = (r[k] for k in ("metrics", "boards", "movers", "potential", "tags", "lifecycle"))
    out: List[Dict[str, Any]] = []

    def say(kind: str, text: str, **ref) -> None:
        out.append({"kind": kind, "text": text, **ref})

    main = "hot" if "hot" in boards["boards"] else next(iter(boards["boards"]), None)
    if main:
        b = boards["boards"][main]
        if b["rows"]:
            first = b["rows"][0]
            extra = f"，比上一期 {fmt_count(first['d_heat'], signed=True)}" if first.get("d_heat") is not None else ""
            say("top", f"{b['label']}第一：《{first['title']}》，热度 {fmt_count(first.get('heat'))}{extra}。", id=first["id"])
        s = b["summary"]
        if m["prev_date"]:
            say("churn", f"{b['label']}今天有 {s['new_entries']} 部新上榜、{s['back_entries']} 部回榜、{s['dropped']} 部掉榜。")

    up = _first(movers["lists"].get("rank_up"))
    if up:
        say("climber", f"名次上升最快：《{up['title']}》在{up['board_label']}上升 {up['value']} 位，到第 {up['rank']} 名。", id=up["id"])
    fav = _first(movers["lists"].get("fav"))
    if fav:
        say("fav", f"收藏涨得最多：《{fav['title']}》一天新增 {fmt_count(fav['value'])} 收藏。", id=fav["id"])
    heat = _first(movers["lists"].get("heat_rate"))
    if heat:
        say("heat", f"热度增速最快：《{heat['title']}》热度日增 {heat['value']:+.1%}。", id=heat["id"])
    new = _first(movers["lists"].get("new_entries"))
    if new:
        n = len(movers["lists"]["new_entries"]["items"])
        say("new", f"共 {n} 部剧首次上榜，排名最高的是《{new['title']}》（{new['board_label']}第 {new['rank']} 名）。", id=new["id"])

    tb = (tags.get("boards") or {}).get(main) or {}
    if tb.get("tags"):
        names = "、".join(t["tag"] for t in tb["tags"][:3])
        say("tag_top", f"{tb['label']}热度最高的题材：{names}。", tag=tb["tags"][0]["tag"])
    if tb.get("rising"):
        t = tb["rising"][0]
        say("tag_up", f"升温最快的题材：{t['tag']}（热度占比 +{t['momentum']:.1f} 个百分点，对比 {tags['baseline_date']}，现有 {t['count']} 部）。", tag=t["tag"])
    if tb.get("falling"):
        t = tb["falling"][0]
        say("tag_down", f"降温最多的题材：{t['tag']}（热度占比 {t['momentum']:.1f} 个百分点）。", tag=t["tag"])
    if tags.get("new_vs_all"):
        t = tags["new_vs_all"][0]
        if (t.get("over_index") or 0) > 1.2:
            say("tag_supply", f"新剧扎堆的题材：{t['tag']}（新剧里占 {t['share_new']:.0%}，老剧里占 {t['share_old']:.0%}）。", tag=t["tag"])

    trend = (life.get("new_heat_trend") or {}).get(main) or []
    if trend and trend[-1]["known"]:
        say("new_share", f"上线 {life['max_age_days']} 天内的新剧贡献了{boards['boards'][main]['label']} {trend[-1]['heat_share']:.0%} 的热度（{trend[-1]['count']} 部）。")
    adapted = [a for a in life.get("adapted", [])]
    if adapted:
        tomato = sum(1 for a in adapted if a["platform"] == "番茄小说")
        say("ip", f"在榜剧里有 {len(adapted)} 部在简介中注明改编自小说，其中番茄小说 {tomato} 部。")
    if potential.get("items"):
        p = potential["items"][0]
        say("potential", f"潜力新剧第一：《{p['title']}》，潜力分 {p['score']:.0f}（{'；'.join(p['reasons'])}）。", id=p["id"])

    if m["history_days"] < 2:
        say("note", "数据才积累了 1 天：名次变化、增量和题材动量从第二天起才有，7 日指标要满一周。")
    return {"date": m["date"], "items": out}
