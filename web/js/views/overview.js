// 总览：今日要点、几个关键数字、收藏涨得最多的剧、潜力新剧、新剧热度占比走势。

import { h } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";
import { lineChart } from "../lib/charts.js";

function insightItem(app, item) {
  const li = h("li", { class: item.kind === "note" ? "note" : "" }, h("span", { class: "dot", "aria-hidden": "true" }));
  const text = h("span");
  if (item.id) {
    // 把句子里的《剧名》做成可点击的链接
    const parts = item.text.split(/(《[^》]+》)/);
    for (const part of parts) {
      if (/^《.+》$/.test(part)) text.append(h("button", { class: "drama-link", type: "button", onclick: () => app.openDrama(item.id) }, part));
      else text.append(part);
    }
  } else if (item.tag) {
    text.append(item.text, " ", h("a", { href: `#/tags?tag=${encodeURIComponent(item.tag)}` }, "看题材"));
  } else {
    text.append(item.text);
  }
  li.append(text);
  return li;
}

export default {
  id: "overview",
  title: "总览",
  async render(root, app) {
    const [insights, boards, movers, potential, lifecycle] = await Promise.all(
      ["insights", "boards", "movers", "potential", "lifecycle"].map((n) => app.data.get(n)),
    );
    const main = boards.boards.hot ? "hot" : Object.keys(boards.boards)[0];
    const b = boards.boards[main];
    const top = b.rows[0];
    const trend = (lifecycle.new_heat_trend || {})[main] || [];
    const newShare = trend.length ? trend[trend.length - 1].heat_share : null;

    root.append(ui.pageHead(`${app.source.label} · ${fmt.shortDate(boards.date)}`, "每天官方榜单刷新后自动更新。点剧名看单剧走势，点题材跳到题材分析。"));
    root.append(h("div", { class: "grid cols-4" },
      ui.kpi(`${b.label}第一`, top ? top.title : "—", top ? `热度 ${fmt.count(top.heat)}` : null, { small: true }),
      ui.kpi("今日新上榜", String(b.summary.new_entries), boards.prev_date ? `回榜 ${b.summary.back_entries} · 掉榜 ${b.summary.dropped}` : "第二天起才有对比"),
      ui.kpi(`${lifecycle.max_age_days} 天内新剧热度占比`, fmt.pct(newShare, 0), `${b.label}里 ${b.summary.new_dramas} 部新剧`),
      ui.kpi(`${b.label}热门题材`, b.summary.top_tags.slice(0, 3).join("、") || "—", "按在榜部数", { small: true }),
    ));

    const list = h("ul", { class: "insights" }, insights.items.map((i) => insightItem(app, i)));
    root.append(h("div", { class: "section" }, ui.card("今日要点", "规则自动生成，可在各分析页核对", list)));

    const favRows = (movers.lists.fav?.items || []).slice(0, 10);
    const potRows = (potential.items || []).slice(0, 10);
    root.append(h("div", { class: "grid cols-2 section" },
      ui.card("收藏涨得最多", "每日新增收藏，最接近「新观众」的信号", ui.table([
        { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
        { key: "value", label: "收藏日增", num: true, render: (r) => ui.signedCount(r.value) },
        { key: "heat", label: "热度", num: true, render: (r) => fmt.count(r.heat) },
        { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags) },
      ], favRows, { emptyText: "第二天起才有增量数据" })),
      ui.card("潜力新剧", `上线 ${potential.max_age_days} 天内或新上榜的剧，按潜力分排序`, ui.table([
        { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
        { key: "score", label: "潜力分", num: true, render: (r) => ui.scoreBar(r.score) },
        { key: "reasons", label: "理由", sortable: false, render: (r) => r.reasons.join("；") },
      ], potRows)),
    ));

    const chartEl = h("div", { class: "chart" });
    const boardsList = Object.keys(lifecycle.new_heat_trend || {});
    const series = boardsList.map((bid, i) => ({
      name: app.boardLabel(bid), slot: i,
      points: lifecycle.new_heat_trend[bid].map((p) => [p.date, p.heat_share]),
    }));
    const trendCard = ui.card(`${lifecycle.max_age_days} 天内新剧的热度占比`, "各榜里新剧贡献的热度比例，越高说明新剧越能打", chartEl);
    root.append(h("div", { class: "section" }, trendCard));
    if (series.length && series[0].points.length > 1) {
      lineChart(chartEl, series, { valueFormat: (v) => fmt.pct(v, 1), axisFormat: (v) => fmt.pct(v, 0), yMin: 0 });
    } else {
      chartEl.replaceWith(ui.empty("积累 2 天以上的数据后显示走势"));
    }
    trendCard.append(h("details", { class: "datatable" }, h("summary", {}, "查看数据表"), ui.table(
      [{ key: "date", label: "日期" }, ...boardsList.map((bid) => ({ key: bid, label: app.boardLabel(bid), num: true, render: (r) => fmt.pct(r[bid], 1) }))],
      (trend || []).map((p, i) => Object.fromEntries([["date", p.date], ...boardsList.map((bid) => [bid, lifecycle.new_heat_trend[bid][i]?.heat_share])])).reverse(),
    )));
  },
};
