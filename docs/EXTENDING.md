# 扩展指南

整个系统分四层，每层都是「注册表 + 插件」，加功能不用改主流程：

```
数据源 Source ──► 快照（统一格式）──► 分析器 Analyzer ──► JSON/CSV ──► 看板页面 View
                                          └──► 报告器 Reporter（简报、推送…）
```

插件可以放在仓库里的任何地方，把模块路径写进 `config.toml` 的 `general.plugins`，启动时会自动导入：

```toml
[general]
plugins = ["plugins.feishu", "plugins.douyin_source"]
```

运行 `python -m radar plugins` 可以看到当前注册了哪些插件。

## 加一个数据源

继承 `radar.sources.base.Source`，实现 `board_labels()` 和 `collect()`，返回统一格式的快照（见 [DATA.md](DATA.md)）：

```python
from radar.core.registry import SOURCES
from radar.sources.base import CollectResult, Source, SCHEMA_VERSION

@SOURCES.register("douyin")
class DouyinSource(Source):
    id = "douyin"
    label = "抖音短剧"

    def board_labels(self):
        return {"hot": "热播榜"}

    def collect(self, batch, force=False, allow_stale=False):
        boards = {"hot": {"label": "热播榜", "items": [{"id": "x1", "rank": 1, "heat": 123}]}}
        items = {"x1": {"title": "…", "tags": ["甜宠"], "heat": 123}}
        snap = {"schema": SCHEMA_VERSION, "source": self.id, "date": batch, "boards": boards, "items": items}
        return CollectResult("new", snap, "ok")
```

然后在 `config.toml` 里加 `[sources.douyin]`。所有分析器和看板页面会自动对新数据源生效，
看板右上角会出现数据源切换。注意遵守对方网站的 robots.txt 和条款，控制请求频率。

## 加一个分析器

分析器是一个函数，接收 `ctx`，返回可以 JSON 序列化的字典，自动写成 `_site/data/<source>/<名字>.json`：

```python
from radar.core.registry import ANALYZERS

@ANALYZERS.register("weekly", depends=["metrics"], order=50)
def weekly(ctx):
    h = ctx.history                      # 全部快照（History 对象）
    m = ctx.results["metrics"]           # 依赖的分析器结果
    ctx.emit("exports/weekly.csv", "…")  # 需要的话可以输出额外文件
    return {"date": m["date"], "items": [...]}
```

- `depends`：依赖的分析器，运行顺序会自动排好。
- `ctx.history`：`latest`、`previous()`、`ago(7)`、`board_days(board)`、`series(id)`、`catalog` 等。
- `ctx.shared`：分析器之间传中间结果，不写文件。
- 不想要某个分析器：`config.toml` 里 `analysis.disabled = ["名字"]`。

## 加一个报告器

报告器在分析完成后运行，适合写简报、推送到群里、发邮件：

```python
import json, os, urllib.request
from radar.core.registry import REPORTERS

@REPORTERS.register("feishu")
def feishu(ctx, settings):
    url = os.environ["FEISHU_WEBHOOK"]          # 密钥放在 GitHub Secrets，不要写进仓库
    lines = [i["text"] for i in ctx.results["insights"]["items"]]
    body = json.dumps({"msg_type": "text", "content": {"text": "\n".join(lines)}}).encode()
    urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}))
    return []
```

```toml
[reporters.feishu]
enabled = true
```

在工作流的 Build 步骤里加 `env: FEISHU_WEBHOOK: ${{ secrets.FEISHU_WEBHOOK }}`。

## 加一个看板页面

在 `web/js/views/` 新建模块，导出 `{ id, title, render(root, app) }`，再加进 `web/js/views/index.js` 的列表：

```js
import * as ui from "../lib/ui.js";

export default {
  id: "weekly",
  title: "周报",
  async render(root, app) {
    const data = await app.data.get("weekly");      // 读 weekly.json
    root.append(ui.pageHead("周报"), ui.card("本周", null, ui.table([
      { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
      { key: "value", label: "数值", num: true },
    ], data.items)));
  },
};
```

可用的工具：`ui.table`（可排序表格）、`ui.card`、`ui.kpi`、`ui.segmented`、`ui.tagChips`、
`charts.lineChart`、`charts.barChart`、`app.openDrama(id)`、`app.setParams({...})`（写进地址栏，可分享）。

图表规则：分类颜色按固定顺序、最多 8 条线；一张图只用一根纵轴（量纲不同就分开画）；每张图下面附数据表。
