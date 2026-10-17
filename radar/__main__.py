"""命令行入口。

    python -m radar collect            采集今天的批次（官方还没刷新时什么都不写）
    python -m radar build              跑分析、生成报告、组装 _site/
    python -m radar run                collect + build
    python -m radar serve              本地预览 _site/
    python -m radar plugins            列出已注册的数据源、分析器、报告器
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import sys
from pathlib import Path
from typing import List

from radar.core.config import load_config
from radar.core.registry import ANALYZERS, REPORTERS, SOURCES, load_plugins
from radar.core.store import Store
from radar.core.timeutil import batch_date
from radar.sources.base import CollectError


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _sources(config, wanted: List[str]) -> List[str]:
    names = wanted or config.enabled_sources()
    for name in names:
        SOURCES.get(name)  # 未知名字直接报错
    return names


def _github_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")


def cmd_collect(config, args) -> int:
    day = args.date or batch_date(config.tz_offset, config.cutoff_hour)
    new_any, failed = False, False
    for sid in _sources(config, args.source):
        store = Store(config.paths, sid)
        source = SOURCES.get(sid).obj(config, store, log)
        log(f"[{sid}] 采集 {day} 的批次")
        try:
            result = source.collect(day, force=args.force, allow_stale=args.allow_stale)
        except CollectError as exc:
            log(f"[{sid}] 失败：{exc}")
            failed = True
            continue
        if result.status == "new":
            path = store.save(result.snapshot)
            new_any = True
            log(f"[{sid}] 已保存 {path.relative_to(config.paths.root)}：{result.message}")
        else:
            log(f"[{sid}] {result.message}")
    _github_output("new_snapshot", "true" if new_any else "false")
    return 1 if failed else 0


def cmd_build(config, args) -> int:
    from radar.site import build_site

    build_site(config, Path(args.out), _sources(config, args.source), log)
    return 0


def cmd_serve(config, args) -> int:
    root = Path(args.out)
    if not root.exists():
        log(f"{root} 不存在，先运行 python -m radar build")
        return 1
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        log(f"预览地址：http://127.0.0.1:{args.port}/  （Ctrl+C 停止）")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def cmd_plugins(config, args) -> int:
    for title, reg in (("数据源", SOURCES), ("分析器", ANALYZERS), ("报告器", REPORTERS)):
        print(f"{title}：")
        for e in reg.entries():
            meta = ", ".join(f"{k}={v}" for k, v in e.meta.items())
            print(f"  - {e.name}" + (f"  ({meta})" if meta else ""))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="短剧雷达")
    parser.add_argument("--config", help="配置文件路径，默认是仓库根目录的 config.toml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p, collect=False, build=False):
        p.add_argument("--source", action="append", default=[], help="只处理这个数据源，可重复")
        if collect:
            p.add_argument("--date", help="批次日期 YYYY-MM-DD，默认按北京时间推算")
            p.add_argument("--force", action="store_true", help="覆盖当天已有的快照")
            p.add_argument("--allow-stale", action="store_true", help="官方没刷新也写快照（会标记为 stale）")
        if build:
            p.add_argument("--out", default="_site", help="站点输出目录")

    common(sub.add_parser("collect", help="采集"), collect=True)
    common(sub.add_parser("build", help="分析并生成站点"), build=True)
    common(sub.add_parser("run", help="采集 + 生成站点"), collect=True, build=True)
    serve = sub.add_parser("serve", help="本地预览")
    serve.add_argument("--out", default="_site")
    serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("plugins", help="列出插件")

    args = parser.parse_args(argv)
    config = load_config(args.config)
    load_plugins(config.general.get("plugins", []))
    if args.cmd == "collect":
        return cmd_collect(config, args)
    if args.cmd == "build":
        return cmd_build(config, args)
    if args.cmd == "run":
        code = cmd_collect(config, args)
        return cmd_build(config, args) or code
    if args.cmd == "serve":
        return cmd_serve(config, args)
    return cmd_plugins(config, args)


if __name__ == "__main__":
    sys.exit(main())
