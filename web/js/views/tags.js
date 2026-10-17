// 题材：哪些题材正热、哪些在升温、新剧扎堆在哪、题材怎么组合、哪类剧最吸收藏。

import { h, clear } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";
import { barChart, lineChart, disposeAll } from "../lib/charts.js";

function dataTable(columns, rows, summary = "查看数据表") {
  return h("details", { class: "datatable" }, h("summary", {}, summary), ui.table(columns, rows));
}

function matrixTable(matrix) {
  const max = Math.max(1, ...matrix.counts.flat());
  const wrap = h("div", { class: "table-wrap" });
  const tbl = h("table");
  tbl.append(h("thead", {}, h("tr", {}, h("th", {}, "题材"), matrix.boards.map((b) => h("th", { class: "num" }, b.label)))));
  const body = h("tbody");
  matrix.tags.forEach((tag, i) => {
    body.append(h("tr", {}, h("td", {}, tag), matrix.counts[i].map((v) => {
      const step = v ? Math.min(6, 1 + Math.floor((v / max) * 5.99)) : 0;
      const style = step ? { background: `var(--seq-${step})`, color: step >= 4 ? "#fff" : "var(--ink)" } : {};
      return h("td", { class: "num heat-cell", style, title: `${tag} · ${v} 部` }, v);
    })));
  });
  tbl.append(body);
  wrap.append(tbl);
  return wrap;
}

export default {
  id: "tags",
  title: "题材",
  async render(root, app) {
    const [data, boards] = await Promise.all([app.data.get("tags"), app.data.get("boards")]);
    const boardIds = Object.keys(data.boards);
    if (!boardIds.length) {
      root.append(ui.empty("还没有题材数据"));
      return;
    }
    let board = boardIds.includes(app.params.get("board")) ? app.params.get("board") : boardIds[0];
    let focus = app.params.get("tag") || "";
    const baseline = data.baseline_date
      ? `动量 = 今天的热度占比 − ${fmt.shortDate(data.baseline_date)} 的热度占比（百分点）`
      : "积累 2 天以上的数据后才有动量";
    root.append(ui.pageHead("题材分析", `一部剧有 3 个题材标签，会同时计入每个标签，所以各题材的占比加起来超过 100%。${baseline}。「${data.format_tags.join("、")}」属于形式标签，不算题材。`));
    const controls = h("div", { class: "controls" });
    const body = h("div");
    root.append(controls, body);
    controls.append(ui.segmented(boardIds.map((b) => ({ value: b, label: data.boards[b].label })), board, (v) => { board = v; app.setParams({ board: v }); draw(); }, "选择榜单"));

    function focusCard(tb) {
      const t = tb.tags.find((x) => x.tag === focus);
      const rows = (boards.boards[board]?.rows || []).filter((r) => (r.tags || []).includes(focus));
      return h("div", { class: "section" }, ui.card(`题材：${focus}`, t ? `${tb.label}里 ${t.count} 部，热度占比 ${fmt.pct(t.heat_share)}，平均名次 ${t.avg_rank}${t.momentum !== undefined ? `，动量 ${fmt.pp(t.momentum)}` : ""}` : `${tb.label}今天没有这个题材的剧`,
        h("p", {}, h("a", { href: "#", onclick: (e) => { e.preventDefault(); focus = ""; app.setParams({ tag: null }); draw(); } }, "× 取消筛选")),
        ui.table([
          { key: "rank", label: "名次", num: true },
          { key: "title", label: "剧名", render: (r) => ui.titleCell(app, r) },
          { key: "heat", label: "热度", num: true, render: (r) => fmt.count(r.heat) },
          { key: "d_fav", label: "收藏日增", num: true, render: (r) => ui.signedCount(r.d_fav) },
          { key: "age_days", label: "上线天数", num: true, render: (r) => fmt.days(r.age_days) },
          { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags) },
        ], rows, { sortKey: "rank" })));
    }

    function draw() {
      disposeAll();
      clear(body);
      const tb = data.boards[board];
      const pick = (t) => { focus = t; app.setParams({ tag: t }); draw(); window.scrollTo({ top: 0, behavior: "smooth" }); };
      const top3 = tb.tags.slice(0, 3).map((t) => t.tag).join("、");
      const up = tb.rising[0];
      const supply = (data.new_vs_all || [])[0];
      body.append(h("div", { class: "grid cols-4" },
        ui.kpi("热度最高的题材", top3 || "—", "按热度占比", { small: true }),
        ui.kpi("升温最快", up ? up.tag : "—", up ? `${fmt.pp(up.momentum)} · ${up.count} 部` : baseline),
        ui.kpi("新剧扎堆", supply ? supply.tag : "—", supply ? `新剧里占 ${fmt.pct(supply.share_new, 0)}，老剧里 ${fmt.pct(supply.share_old, 0)}` : "新剧太少，暂不判断"),
        ui.kpi("参与统计的新剧", String(data.new_dramas), `上线天数不超过设定值或标注「新剧」`),
      ));
      if (focus) body.append(focusCard(tb));

      // 题材热度占比（条形图 + 完整数据表）
      const barEl = h("div", { class: "chart" });
      const topTags = tb.tags.slice(0, 15);
      const tagColumns = [
        { key: "tag", label: "题材", render: (r) => h("button", { class: "chip", type: "button", onclick: () => pick(r.tag) }, r.tag) },
        { key: "count", label: "部数", num: true },
        { key: "heat_share", label: "热度占比", num: true, render: (r) => fmt.pct(r.heat_share) },
        { key: "count_share", label: "部数占比", num: true, render: (r) => fmt.pct(r.count_share) },
        { key: "avg_rank", label: "平均名次", num: true },
        { key: "momentum", label: "动量", num: true, render: (r) => h("span", { class: fmt.trendClass(r.momentum) }, fmt.pp(r.momentum)) },
        { key: "count_delta", label: "部数变化", num: true, render: (r) => ui.signedCount(r.count_delta) },
        { key: "top", label: "代表作", sortable: false, render: (r) => h("span", { class: "tags" }, (r.top || []).map((x) => ui.dramaLink(app, x))) },
      ];
      body.append(h("div", { class: "section" }, ui.card(`${tb.label} · 题材热度占比`, "带这个标签的剧的热度之和 ÷ 全榜热度。点题材可筛出对应的剧", barEl, dataTable(tagColumns, tb.tags, `查看全部 ${tb.tags.length} 个题材`))));
      barChart(barEl, topTags.map((t) => ({ label: t.tag, value: t.heat_share })), { valueFormat: (v) => fmt.pct(v, 1), axisFormat: (v) => fmt.pct(v, 0) });

      // 升温 / 降温
      const moveCols = (cls) => [
        { key: "tag", label: "题材", render: (r) => h("button", { class: "chip", type: "button", onclick: () => pick(r.tag) }, r.tag) },
        { key: "momentum", label: "动量", num: true, render: (r) => h("span", { class: cls }, fmt.pp(r.momentum)) },
        { key: "heat_share", label: "当前占比", num: true, render: (r) => fmt.pct(r.heat_share) },
        { key: "count", label: "部数", num: true },
        { key: "count_delta", label: "部数变化", num: true, render: (r) => ui.signedCount(r.count_delta) },
      ];
      body.append(h("div", { class: "grid cols-2 section" },
        ui.card("升温最快", baseline, ui.table(moveCols("up"), tb.rising, { emptyText: "积累 2 天以上的数据后显示" })),
        ui.card("降温最多", baseline, ui.table(moveCols("down"), tb.falling, { emptyText: "积累 2 天以上的数据后显示" })),
      ));

      // 走势：当前热度占比前 8 的题材，颜色按这个固定顺序分配
      const lineEl = h("div", { class: "chart tall" });
      const trendTags = Object.keys(tb.series).slice(0, 8);
      const trendCard = ui.card("题材热度占比走势", "当前热度占比前 8 的题材；点图例可隐藏某条线", lineEl);
      body.append(h("div", { class: "section" }, trendCard));
      const dates = (tb.series[trendTags[0]] || []).map((p) => p.date);
      if (dates.length > 1) {
        lineChart(lineEl, trendTags.map((t, i) => ({ name: t, slot: i, points: tb.series[t].map((p) => [p.date, p.heat_share]) })), { valueFormat: (v) => fmt.pct(v, 1), axisFormat: (v) => fmt.pct(v, 0), yMin: 0 });
        trendCard.append(dataTable(
          [{ key: "date", label: "日期" }, ...trendTags.map((t) => ({ key: t, label: t, num: true, render: (r) => fmt.pct(r[t], 1) }))],
          dates.map((d, i) => Object.fromEntries([["date", d], ...trendTags.map((t) => [t, tb.series[t][i]?.heat_share])])).reverse(),
        ));
      } else {
        lineEl.replaceWith(ui.empty("积累 2 天以上的数据后显示走势"));
      }

      // 新剧扎堆、题材组合
      body.append(h("div", { class: "grid cols-2 section" },
        ui.card("新剧扎堆的题材", "超配倍数 = 新剧里带这个题材的比例 ÷ 老剧里的比例；大于 1 说明新剧在往这个方向挤，「仅新剧」表示老剧里没有", ui.table([
          { key: "tag", label: "题材", render: (r) => h("button", { class: "chip", type: "button", onclick: () => pick(r.tag) }, r.tag) },
          { key: "over_index", label: "超配倍数", num: true, value: (r) => r.over_index ?? 99, render: (r) => (r.over_index ? `${r.over_index.toFixed(2)}×` : "仅新剧") },
          { key: "new_count", label: "新剧部数", num: true },
          { key: "share_new", label: "新剧中占比", num: true, render: (r) => fmt.pct(r.share_new, 0) },
          { key: "share_old", label: "老剧中占比", num: true, render: (r) => fmt.pct(r.share_old, 0) },
        ], data.new_vs_all, { sortKey: "over_index", sortDir: "desc", emptyText: "新剧太少" })),
        ui.card("常见题材组合", "同一部剧上同时出现的两个题材（按今天所有在榜剧去重统计）", ui.table([
          { key: "tags", label: "组合", value: (r) => r.tags.join("+"), render: (r) => ui.tagChips(r.tags, pick) },
          { key: "count", label: "部数", num: true },
          { key: "avg_heat", label: "平均热度", num: true, render: (r) => fmt.count(r.avg_heat) },
        ], data.pairs, { sortKey: "count", sortDir: "desc", limit: 12 })),
      ));

      body.append(h("div", { class: "grid cols-2 section" },
        ui.card("题材 × 类型", "真人剧、AI 剧、漫剧三个榜里各题材的部数，颜色越深越多", data.matrix.tags.length ? matrixTable(data.matrix) : ui.empty()),
        ui.card("题材吸粉能力", "带这个题材的在榜剧平均每天新增多少收藏（至少 3 部才统计）", ui.table([
          { key: "tag", label: "题材", render: (r) => h("button", { class: "chip", type: "button", onclick: () => pick(r.tag) }, r.tag) },
          { key: "avg_d_fav", label: "平均收藏日增", num: true, render: (r) => ui.signedCount(r.avg_d_fav) },
          { key: "avg_heat", label: "平均热度", num: true, render: (r) => fmt.count(r.avg_heat) },
          { key: "avg_rating", label: "平均评分", num: true, render: (r) => fmt.rating(r.avg_rating) },
          { key: "count", label: "部数", num: true },
        ], data.efficiency, { limit: 12 })),
      ));
    }
    draw();
  },
};
