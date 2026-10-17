"""每日 Markdown 简报：reports/<source>/YYYY-MM-DD.md。在 GitHub 上直接能看，也方便以后转发到群里。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from radar.analysis.util import fmt_count
from radar.core.registry import REPORTERS


def _cell(text: Any) -> str:
    return str(text if text is not None else "—").replace("|", "／").replace("\n", " ")


def _table(header: List[str], rows: List[List[Any]]) -> List[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def render(ctx) -> str:
    r = ctx.results
    date = r["metrics"]["date"]
    lines = [f"# {ctx.source.label} · {date} 简报", ""]
    lines += [f"- {i['text']}" for i in r["insights"]["items"]] + [""]

    hot = r["boards"]["boards"].get("hot")
    if hot:
        lines += [f"## {hot['label']}前 20", ""]
        rows = []
        for x in hot["rows"][:20]:
            delta = "NEW" if x.get("badge") == "new" else (f"{x['delta']:+d}" if x.get("delta") else "")
            rows.append([x["rank"], delta, x["title"], fmt_count(x.get("heat")), fmt_count(x.get("d_heat"), True), "、".join(x.get("tags", []))])
        lines += _table(["名次", "变化", "剧名", "热度", "热度日增", "题材"], rows) + [""]

    fav = r["movers"]["lists"].get("fav", {}).get("items", [])
    if fav:
        lines += ["## 收藏日增前 10", ""]
        lines += _table(["剧名", "收藏日增", "热度", "题材"], [[x["title"], fmt_count(x["value"], True), fmt_count(x.get("heat")), "、".join(x.get("tags", []))] for x in fav[:10]]) + [""]

    pot = r["potential"].get("items", [])
    if pot:
        lines += ["## 潜力新剧前 10", ""]
        lines += _table(["剧名", "潜力分", "理由", "上线天数"], [[x["title"], x["score"], "；".join(x["reasons"]), x.get("age_days")] for x in pot[:10]]) + [""]

    tb = r["tags"].get("boards", {}).get("hot")
    if tb and tb.get("tags"):
        lines += ["## 题材热度（热播榜）", ""]
        rows = [[t["tag"], t["count"], f"{t['heat_share']:.1%}", (f"{t['momentum']:+.1f}" if t.get("momentum") is not None else "—")] for t in tb["tags"][:15]]
        lines += _table(["题材", "部数", "热度占比", "动量（百分点）"], rows) + [""]
    lines.append("数据来自官方公开榜单，由 drama-radar 自动生成。")
    return "\n".join(lines) + "\n"


@REPORTERS.register("markdown")
def markdown(ctx, settings: Dict[str, Any]) -> List[Path]:
    folder = ctx.config.paths.reports / ctx.source.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ctx.results['metrics']['date']}.md"
    path.write_text(render(ctx), encoding="utf-8")
    return [path]
