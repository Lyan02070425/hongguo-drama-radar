"""把 hongguo-radar（https://github.com/2252399314-cyber/hongguo-radar）的历史快照转成本项目的格式。

用法：
    git clone https://github.com/2252399314-cyber/hongguo-radar /tmp/hongguo-radar
    python3 scripts/import_hongguo_radar.py /tmp/hongguo-radar            # 预览
    python3 scripts/import_hongguo_radar.py /tmp/hongguo-radar --write    # 写入 data/

规则：
- 本项目已有的日期不覆盖（自己采集的数据更完整）。
- 题材：优先用本项目目录里记下的榜单页 3 个分类；没有的取对方标签的前 3 个（经核对，对方标签的前 3 个和榜单页分类一致的约占 96%）。
- 榜单条目的热度取整到万，和榜单页显示的口径一致；单剧热度保留精确值。
- 对方详情页抓取失败（null）的剧不写入 items，但保留它的榜单名次。
- 导入的快照带 "imported_from": "hongguo-radar" 标记。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar.core.config import load_config  # noqa: E402
from radar.core.store import Store  # noqa: E402
from radar.core.text import clean_tags  # noqa: E402
from radar.core.timeutil import ts_to_date  # noqa: E402
from radar.sources.base import SCHEMA_VERSION  # noqa: E402
from radar.sources.hongguo.source import BOARDS  # noqa: E402


def round_wan(value):
    return int(round(value / 10_000) * 10_000) if value else None


def convert(src: dict, catalog: dict, tz: int) -> dict:
    series = src.get("series") or {}
    boards, status_tags, on = {}, {}, {}
    for board, data in (src.get("ranks") or {}).items():
        if board not in BOARDS:
            continue
        items = []
        for x in data.get("items", []):
            hot = (series.get(x["id"]) or {}).get("hot")
            items.append({"id": x["id"], "rank": x["rank"], "heat": round_wan(hot)})
            status_tags.setdefault(x["id"], [])
            for t in x.get("status_tags") or []:
                if t not in status_tags[x["id"]]:
                    status_tags[x["id"]].append(t)
            on.setdefault(x["id"], []).append(board)
        boards[board] = {"label": BOARDS[board][1], "label_date": data.get("label_date"), "items": items}

    items = {}
    for sid, s in series.items():
        if not s:
            continue
        theirs = clean_tags(s.get("tags"))
        item = {
            "title": s.get("title"),
            "tags": (catalog.get(sid) or {}).get("tags") or theirs[:3],
            "detail_tags": theirs,
            "status_tags": status_tags.get(sid, []),
            "heat": s.get("hot"),
            "heat_exact": s.get("hot") is not None,
            "fav": s.get("fav"),
            "like": s.get("like"),
            "rating": s.get("score"),
            "rating_count": s.get("rating_cnt"),
            "review_count": s.get("review_cnt"),
            "episodes": s.get("eps"),
            "status_code": s.get("status"),
            "first_visible": ts_to_date(s.get("first_visible"), tz),
            "tracked_by": sorted(set(on.get(sid, [])) | {"detail"}),
        }
        items[sid] = {k: v for k, v in item.items() if v is not None}
    return {
        "schema": SCHEMA_VERSION,
        "source": "hongguo",
        "date": src["date"],
        "fetched_at": src.get("fetched_at"),
        "stale": False,
        "boards": boards,
        "items": items,
        "watchlist": [],
        "errors": src.get("errors") or [],
        "requests": None,
        "imported_from": "hongguo-radar",
    }


def update_catalog(catalog: dict, snap: dict) -> None:
    day = snap["date"]
    on = {}
    for board, data in snap["boards"].items():
        for x in data["items"]:
            on.setdefault(x["id"], set()).add(board)
    for sid, it in snap["items"].items():
        entry = catalog.setdefault(sid, {"first_seen": day, "last_seen": day})
        entry["first_seen"] = min(entry.get("first_seen", day), day)
        if day >= entry.get("last_seen", day):
            entry["last_seen"] = day
        entry.setdefault("title", it.get("title"))
        entry.setdefault("tags", it.get("tags"))
        entry.setdefault("detail_tags", it.get("detail_tags"))
        for key in ("first_visible", "episodes"):
            if it.get(key) and not entry.get(key):
                entry[key] = it[key]
        boards = on.get(sid, set())
        entry["boards_seen"] = sorted(set(entry.get("boards_seen", [])) | boards)
        if boards and day > entry.get("last_on_board", ""):
            entry["last_on_board"] = day


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", help="hongguo-radar 仓库的本地路径")
    parser.add_argument("--write", action="store_true", help="真正写入（默认只预览）")
    args = parser.parse_args()
    config = load_config()
    store = Store(config.paths, "hongguo")
    catalog = store.load_catalog()
    existing = set(store.dates())
    files = sorted(Path(args.repo, "data", "snapshots").glob("????-??-??.json"))
    if not files:
        print("没有找到 data/snapshots/*.json")
        return 1
    imported = []
    for path in files:
        src = json.loads(path.read_text(encoding="utf-8"))
        if src["date"] in existing:
            print(f"{src['date']}：本项目已有，跳过")
            continue
        snap = convert(src, catalog, config.tz_offset)
        sizes = {b: len(d["items"]) for b, d in snap["boards"].items()}
        print(f"{src['date']}：{len(snap['items'])} 部剧，榜单 {sizes}，对方错误 {len(snap['errors'])} 个")
        imported.append(snap)
    if args.write:
        for snap in imported:
            store.save(snap)
            update_catalog(catalog, snap)
        store.save_catalog(catalog)
        print(f"已写入 {len(imported)} 份快照，目录现有 {len(catalog)} 部剧")
    else:
        print("预览完成，加 --write 写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
