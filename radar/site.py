"""组装静态站点 _site/：复制 web/，对每个数据源跑分析器和报告器，写 manifest。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List

from radar.analysis.history import History
from radar.analysis.runner import Context, run_analyzers
from radar.core.config import Config
from radar.core.registry import ANALYZERS, REPORTERS, SOURCES
from radar.core.store import Store, write_json
from radar.core.timeutil import shift, utc_stamp


def analyze_source(config: Config, source_id: str, out: Path, log: Callable[[str], None] = print) -> Dict[str, Any]:
    store = Store(config.paths, source_id)
    source = SOURCES.get(source_id).obj(config, store, log)
    dates = store.dates()
    entry: Dict[str, Any] = {"id": source_id, "label": source.label, "boards": source.board_labels(), "latest_date": None}
    if not dates:
        log(f"[{source_id}] 还没有快照，跳过分析")
        return entry
    window = int(config.general.get("history_window_days", 400))
    history = History(source_id, store.load_range(start=shift(dates[-1], -window)), store.load_catalog(),
                      board_order=list(source.board_labels()))
    ctx = Context(source=source, history=history, config=config)
    log(f"[{source_id}] 分析 {len(history.dates)} 天的快照（{history.dates[0]} ~ {history.dates[-1]}）")
    data_dir = out / "data" / source_id
    run_analyzers(ctx, data_dir, log)

    for name, settings in config.reporters.items():
        if not settings.get("enabled", False):
            continue
        written = REPORTERS.get(name).obj(ctx, settings)
        log(f"  报告器 {name}：{', '.join(p.name for p in written)}")

    report_dir = config.paths.reports / source_id
    reports: List[str] = []
    if report_dir.exists():
        target = out / "reports" / source_id
        target.mkdir(parents=True, exist_ok=True)
        for md in sorted(report_dir.glob("*.md"), reverse=True):
            shutil.copy2(md, target / md.name)
            reports.append(md.stem)
    entry.update(
        latest_date=history.dates[-1],
        first_date=history.dates[0],
        history_days=len(history.dates),
        outputs=[n for n in ctx.results if ANALYZERS.get(n).meta.get("write", True)],
        reports=reports,
    )
    return entry


def _bust_cache(out: Path, stamp: str) -> None:
    """给 index.html 里引用的样式和脚本加版本号，重新部署后浏览器不会用旧缓存。"""
    index = out / "index.html"
    version = "".join(ch for ch in stamp if ch.isdigit())
    html = index.read_text(encoding="utf-8")
    for asset in ("css/style.css", "js/app.js"):
        html = html.replace(f'"{asset}"', f'"{asset}?v={version}"')
    index.write_text(html, encoding="utf-8")


def build_site(config: Config, out: Path, sources: List[str], log: Callable[[str], None] = print) -> Dict[str, Any]:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(config.paths.web, out)
    (out / ".nojekyll").write_text("")
    stamp = utc_stamp()
    _bust_cache(out, stamp)
    manifest = {
        "title": config.general.get("site_title", "短剧雷达"),
        "generated_at": stamp,
        "sources": [analyze_source(config, sid, out, log) for sid in sources],
    }
    write_json(out / "data" / "manifest.json", manifest, sort_keys=False)
    log(f"站点已生成：{out}")
    return manifest
