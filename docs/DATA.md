# 数据格式与口径

## 原始快照 `data/snapshots/<source>/YYYY-MM-DD.json`

每个批次一份，只追加不修改，是唯一的原始数据。所有数据源用同一个格式，分析器只依赖这个格式。

```json
{
  "schema": 1,
  "source": "hongguo",
  "date": "2026-10-17",            // 批次日期（北京时间 9 点前抓到的算前一天）
  "fetched_at": "2026-10-17T03:10:00Z",
  "stale": false,                  // true = 用 --allow-stale 写出、官方榜单未刷新
  "boards": {
    "hot": {"label": "热播榜", "label_date": "2026-10-17",
            "items": [{"id": "7696…", "rank": 1, "heat": 92000000}]}   // heat 为榜单页显示值，取整到万
  },
  "items": {
    "7696…": {
      "title": "…", "tags": ["玄幻", "穿越", "修真"], "status_tags": ["新剧"],
      "heat": 92004321, "heat_exact": true,     // 有详情页时是精确值
      "fav": 823000, "like": 2286000, "rating": 9.0,
      "rating_count": 4347, "review_count": 1458,
      "episodes": 80, "first_visible": "2026-10-14",
      "detail_tags": ["玄幻"], "tracked_by": ["ai", "detail", "hot"]
    }
  },
  "watchlist": [{"entry": "首辅娇娘", "status": "ok", "id": "7686…"}],
  "errors": [{"stage": "detail", "id": "…", "message": "HTTP 500"}],
  "requests": 342
}
```

迁移自 hongguo-radar 的快照（2026-10-13 至 10-16）带 `"imported_from": "hongguo-radar"`，`requests` 为空；题材优先取本项目记下的榜单页分类，没有的取对方标签的前 3 个。

`items` 包含：今天在任意榜上的剧、观察列表里的剧、最近 14 天上过榜但今天掉榜的剧（继续追踪，便于看掉榜后的走势）。

## 剧集目录 `data/catalog/<source>.json`

每部剧不常变的信息：标题、题材、简介、封面、上线日期、集数、演员、改编来源（从简介里识别「改编自…《…》，作者…」）、
首次和最后出现日期、上过哪些榜。每次采集更新。

## 分析输出 `_site/data/<source>/*.json`

由 `python -m radar build` 从快照重新计算，不提交到 git。看板读这些文件。

| 文件 | 内容 |
|---|---|
| `status.json` | 最新批次、历史天数、各榜日期、错误 |
| `metrics.json` | 基础指标：每个榜的名次变化，每部剧的增量和增速（其他分析的基础） |
| `boards.json` | 榜单页：每个榜的完整排名 + 汇总 |
| `movers.json` | 飙升页：按各种口径排序的列表 |
| `potential.json` | 潜力新剧 |
| `tags.json` | 题材分析 |
| `lifecycle.json` | 内容结构：剧龄、集数、改编来源、新剧热度占比走势 |
| `dramas.json` + `dramas/<id>.json` | 剧集索引和单剧历史 |
| `insights.json` | 今日要点 |
| `exports.json` + `exports/*.csv` | CSV 导出 |

## 口径

- **热度**：官方按站内观看和互动综合计算的分数，每天批量刷新一次，不是播放量，可升可降。
- **日增**：今天 − 上一期；两期间隔多天时按天平均。收藏、点赞、评分人数、评论数是累计值，所以日增 ≈ 当天新增。
- **热度增长率**：热度日增 ÷ 上一期热度；上一期热度低于 `min_heat_for_rate` 的不计，避免小基数虚高。
- **名次变化**：只在官方刷新过的榜单日之间比较（`stale` 快照不计）。正数表示上升。
- **NEW / 回榜**：NEW = 采集以来第一次上这个榜；回榜 = 上一期不在、更早上过。
- **新剧**：上线天数 ≤ `new_drama_max_age_days`，或官方标注了「新剧」。
- **题材**：榜单页的 3 个分类标签，一部剧计入每个标签，所以占比之和超过 100%。「漫剧」等形式标签在 `format_tags` 里配置，不算题材。
- **热度占比**：带这个题材的剧的热度之和 ÷ 全榜热度之和。
- **动量**：今天的热度占比 − 约 N 天前（`tag_momentum_days`）的热度占比，单位百分点。不足 N 天时和最早一份比。
- **超配倍数**：新剧里带这个题材的比例 ÷ 老剧（非新剧）里的比例；> 1 表示新剧在往这个题材挤。
- **潜力分**：候选剧（新剧或新上榜）里，收藏日增、热度增长率、名次上升、评分四项的百分位加权平均，0–100。

## CSV（`exports/`，UTF-8 带 BOM）

- `drama_daily.csv`：每天每部被追踪的剧一行。
- `board_daily.csv`：每天每个榜的完整排名。
- `tag_daily.csv`：每天每个榜每个题材的部数、热度、占比、平均名次。
- `catalog.csv`：剧集目录。

pandas 示例：

```python
import pandas as pd
base = "https://<用户名>.github.io/<仓库>/data/hongguo/exports"
daily = pd.read_csv(f"{base}/drama_daily.csv", encoding="utf-8-sig")
tags = pd.read_csv(f"{base}/tag_daily.csv", encoding="utf-8-sig")
tags[tags.board == "hot"].pivot(index="date", columns="tag", values="heat_share")
```
