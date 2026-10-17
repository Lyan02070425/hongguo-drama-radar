// 数据：CSV 下载、每日简报、口径说明和采集状态。

import { h } from "../lib/dom.js";
import * as ui from "../lib/ui.js";

export default {
  id: "data",
  title: "数据下载",
  icon: "data",
  async render(root, app) {
    const [exportsInfo, status] = await Promise.all([app.data.get("exports"), app.data.get("status")]);
    root.append(ui.pageHead("数据下载", "长表格式的 CSV（UTF-8 带 BOM，Excel 直接打开不乱码），可以拿去做自己的分析。"));
    root.append(ui.card("CSV 文件", null, h("ul", { class: "files" }, exportsInfo.files.map((f) => h("li", {},
      h("a", { href: app.data.url(f.path), download: "" }, f.label), ` · ${f.rows.toLocaleString("zh-CN")} 行 · ${f.desc}`,
      h("div", { class: "legend-note" }, "列：", f.columns.join(", ")),
    )))));

    const reports = app.source.reports || [];
    root.append(h("div", { class: "section" }, ui.card("每日简报", "Markdown 格式，仓库的 reports/ 目录里也有", reports.length
      ? h("ul", { class: "files" }, reports.slice(0, 30).map((d) => h("li", {}, h("a", { href: `reports/${encodeURIComponent(app.source.id)}/${d}.md`, target: "_blank", rel: "noopener" }, `${d} 简报`))))
      : ui.empty("还没有简报"))));

    root.append(h("div", { class: "section" }, ui.card("口径说明", null, h("ul", {},
      h("li", {}, "热度：官方按站内观看和互动综合计算的分数，每天批量刷新一次，不是播放量。榜单页显示的热度取整到万，详情页的是精确值。"),
      h("li", {}, "收藏、点赞、评分人数、评论数是累计值，日增 = 今天 − 上一期（间隔多天时按天平均）。收藏日增最接近「新观众」的信号。"),
      h("li", {}, "名次变化只在官方刷新过的榜单日之间比较；NEW = 采集以来第一次上这个榜。"),
      h("li", {}, "新剧：上线天数不超过 config.toml 里设定的天数，或者官方标注了「新剧」。上线日期取自详情页。"),
      h("li", {}, "题材：榜单页每部剧的 3 个分类标签。一部剧计入每个标签，所以占比加起来会超过 100%。"),
      h("li", {}, "潜力分：几项指标在候选剧里的百分位加权平均，是透明的经验规则，不是预测。"),
    ))));

    const errors = status.errors || [];
    root.append(h("div", { class: "section" }, ui.card("采集状态", `最近一次：${status.fetched_at || "—"} · 请求 ${status.requests ?? "—"} 次 · 错误 ${status.error_count} 个`,
      ui.table([
        { key: "board", label: "榜单" },
        { key: "label_date", label: "页面标注日期" },
        { key: "count", label: "抓到部数", num: true },
      ], Object.entries(status.boards).map(([b, v]) => ({ board: v.label, label_date: v.label_date, count: v.count }))),
      errors.length ? h("details", { class: "datatable" }, h("summary", {}, `查看 ${errors.length} 个错误`), ui.table([
        { key: "stage", label: "阶段" }, { key: "id", label: "对象" }, { key: "message", label: "信息", wrap: true },
      ], errors)) : null,
      (status.watchlist || []).length ? h("div", { class: "section" }, h("h2", {}, "观察列表"), ui.table([
        { key: "entry", label: "条目" }, { key: "status", label: "解析结果" }, { key: "id", label: "编号" },
      ], status.watchlist)) : null,
    )));
  },
};
